"""Local credential cache for ``secai-cli login``.

Stores the tenant URL and token (and, see below, the OAuth2 identity used to
obtain it) in the OS-native secret store when available, falling back to a
plaintext ``~/.config/secai/credentials.json`` file (mode 0600) so users can
authenticate once instead of exporting ``SECAI_TENANT_URL``/``SECAI_TOKEN``
for every shell session.

Precedence when resolving credentials for a command: explicit
``SECAI_TENANT_URL``/``SECAI_TOKEN`` environment variables always win (so CI
and scripted usage is unaffected); the cached login is used only as a
fallback when those env vars are unset.

When ``login`` performs the OAuth2 exchange (as opposed to being given a
raw ``--token``), the service-account ``identity_url``/``client_id``/
``client_secret`` used to obtain it are cached alongside the token too.
This lets ``build_token_refresher()`` silently mint a new token (and
persist it) the next time the cached one expires and returns HTTP 401,
without requiring the user to run ``secai-cli login`` again. This makes the
cache at least as sensitive as the service-account secret itself, not just
the short-lived token, regardless of which backend stores it.

**Storage backend:** credentials are stored via the ``keyring`` package
(a required dependency) whenever a usable backend is actually available
(macOS Keychain and Windows Credential Locker work out of the box; Linux
needs a running Secret Service daemon such as GNOME Keyring or KWallet,
which headless servers/containers/CI typically don't have). There is no
platform check here — each `login`/`load_credentials()`/`clear_credentials()`
call simply *tries* the keyring and transparently falls back to the
plaintext file when it isn't usable, so the right thing happens on each
platform without any configuration. Set ``SECAI_NO_KEYRING=1`` to always use
the plaintext file even when a keyring backend would work — useful on
headless Linux/CI to skip the (failed) keyring attempt outright. A
credentials file left over from a prior run where no keyring backend was
available is opportunistically migrated into the keyring (and then
deleted) the next time one becomes usable.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Callable

import httpx

_CONFIG_DIR = Path(os.environ.get("SECAI_CONFIG_DIR", "~/.config/secai")).expanduser()
_CREDENTIALS_FILE = _CONFIG_DIR / "credentials.json"
_KEYRING_SERVICE = "secai-cli"
_KEYRING_USERNAME = "credentials"

# Sentinel distinguishing "not yet attempted" from "attempted and unavailable"
# so repeated calls within one CLI invocation don't re-import/re-probe.
_NOT_LOADED = object()
_keyring_module_cache: Any = _NOT_LOADED


def _import_keyring() -> Any | None:
    """Import and return the ``keyring`` module, or None if unavailable.

    Honors ``SECAI_NO_KEYRING`` as an explicit opt-out. ``keyring`` is a
    required dependency, so the only normal reason this returns ``None`` is
    that opt-out; the ``ImportError`` guard is defensive (e.g. a broken or
    manually-stripped install) rather than an expected code path.
    """
    global _keyring_module_cache
    if _keyring_module_cache is not _NOT_LOADED:
        return _keyring_module_cache
    if os.environ.get("SECAI_NO_KEYRING"):
        _keyring_module_cache = None
        return None
    try:
        import keyring as _keyring
    except ImportError:
        _keyring_module_cache = None
        return None
    _keyring_module_cache = _keyring
    return _keyring


def _keyring_get_raw() -> str | None:
    """Best-effort read from the OS keyring. Never raises, never warns."""
    kr = _import_keyring()
    if kr is None:
        return None
    try:
        return kr.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)  # type: ignore[no-any-return]
    except Exception:
        return None


def _keyring_set_raw(payload: str, *, warn_on_failure: bool) -> bool:
    """Best-effort write to the OS keyring. Returns True on success.

    Only warns when *warn_on_failure* is set — i.e. for the deliberate
    ``secai-cli login`` save, not for opportunistic background migration
    attempts, which should stay silent.
    """
    kr = _import_keyring()
    if kr is None:
        return False
    try:
        kr.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, payload)
    except Exception as exc:
        if warn_on_failure:
            print(
                f"[secai-cli] OS keyring unavailable ({exc}); falling back to a "
                f"plaintext credentials file at {_CREDENTIALS_FILE} (mode 0600). "
                "This is common on headless Linux without a Secret Service "
                "daemon running. Set SECAI_NO_KEYRING=1 to silence this warning "
                "and always use the plaintext file.",
                file=sys.stderr,
            )
        return False
    return True


def _keyring_delete_raw() -> bool:
    """Best-effort delete from the OS keyring. Returns True on success."""
    kr = _import_keyring()
    if kr is None:
        return False
    try:
        kr.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except Exception:
        return False
    return True


def _keyring_usable() -> bool:
    """Read-only probe for whether the OS keyring backend actually works."""
    kr = _import_keyring()
    if kr is None:
        return False
    try:
        kr.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except Exception:
        return False
    return True


def active_backend() -> str:
    """Describe where ``secai-cli login`` would store credentials right now."""
    if _keyring_usable():
        kr = _import_keyring()
        assert kr is not None
        try:
            name = type(kr.get_keyring()).__name__
        except Exception:
            name = "keyring"
        return f"OS keyring ({name})"
    return f"plaintext file (0600) at {_CREDENTIALS_FILE}"


class TokenFetchError(RuntimeError):
    """Raised when the OAuth2 client_credentials token exchange fails."""


def fetch_access_token(
    identity_url: str,
    client_id: str,
    client_secret: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Exchange service-account credentials for a bearer access token.

    Performs an OAuth2 ``client_credentials`` grant against
    ``{identity_url}/oauth2/platformtoken``, so ``secai-cli login`` never
    requires pasting a raw JWT by hand.
    """
    url = f"{identity_url.rstrip('/')}/oauth2/platformtoken"
    try:
        response = httpx.post(
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise TokenFetchError(f"could not reach {url}: {exc}") from exc

    if response.status_code != 200:
        raise TokenFetchError(
            f"authentication failed for service account {client_id} "
            f"(HTTP {response.status_code}): {response.text}"
        )

    try:
        return str(response.json()["access_token"])
    except (json.JSONDecodeError, KeyError) as exc:
        raise TokenFetchError(f"unexpected response from {url}: missing access_token") from exc


def credentials_path() -> Path:
    """Return the path to the local credentials file."""
    return _CREDENTIALS_FILE


def save_credentials(
    tenant_url: str,
    token: str,
    *,
    identity_url: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> None:
    """Persist credentials, preferring the OS keyring over a plaintext file.

    ``identity_url``/``client_id``/``client_secret`` are optional and only
    present when ``login`` performed the OAuth2 exchange; they enable
    automatic token refresh on expiry via ``build_token_refresher()``.

    Tries the OS keyring first and falls back to a 0600 plaintext file at
    ``~/.config/secai/credentials.json`` when ``keyring`` isn't installed, no
    backend is usable, or ``SECAI_NO_KEYRING`` is set (see module docstring).
    """
    data: dict[str, str] = {"tenant_url": tenant_url, "token": token}
    if identity_url and client_id and client_secret:
        data["identity_url"] = identity_url
        data["client_id"] = client_id
        data["client_secret"] = client_secret

    if _keyring_set_raw(json.dumps(data), warn_on_failure=True):
        # Stored in the OS keyring; drop any stale plaintext file left over
        # from an earlier file-based login so it can't linger/shadow it.
        if _CREDENTIALS_FILE.exists():
            _CREDENTIALS_FILE.unlink()
        return

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    _CREDENTIALS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def load_credentials() -> dict[str, str] | None:
    """Load cached credentials, or None if no login has been saved.

    Includes ``identity_url``/``client_id``/``client_secret`` when present
    (i.e. the cached login was obtained via the OAuth2 exchange).

    Checks the OS keyring first, then falls back to the plaintext file. If
    credentials are found only in the plaintext file *and* the keyring is
    now usable (e.g. ``keyring`` was installed after an earlier file-based
    login), they're opportunistically migrated into the keyring and the
    plaintext file is removed.
    """
    raw = _keyring_get_raw()
    migrate = False
    data: Any = None
    if raw is not None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    elif _CREDENTIALS_FILE.exists():
        try:
            data = json.loads(_CREDENTIALS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            data = None
        else:
            migrate = True

    if not isinstance(data, dict) or "tenant_url" not in data or "token" not in data:
        return None

    if migrate and _keyring_set_raw(json.dumps(data), warn_on_failure=False):
        with contextlib.suppress(OSError):
            _CREDENTIALS_FILE.unlink()

    result = {"tenant_url": data["tenant_url"], "token": data["token"]}
    for key in ("identity_url", "client_id", "client_secret"):
        if data.get(key):
            result[key] = data[key]
    return result


def clear_credentials() -> bool:
    """Remove cached credentials from both the OS keyring and the plaintext file.

    Returns True if anything was removed.
    """
    removed = _keyring_delete_raw()
    if _CREDENTIALS_FILE.exists():
        _CREDENTIALS_FILE.unlink()
        removed = True
    return removed


def resolve_credentials() -> tuple[str | None, str | None]:
    """Resolve (tenant_url, token) using env vars first, then the cached login.

    Env vars (``SECAI_TENANT_URL``/``SECAI_TOKEN``) always take precedence so
    CI/scripted usage is unaffected by a previously cached ``secai-cli login``.
    """
    env_url = os.environ.get("SECAI_TENANT_URL")
    env_token = os.environ.get("SECAI_TOKEN")
    if env_url and env_token:
        return env_url, env_token

    cached = load_credentials()
    if cached:
        return env_url or cached["tenant_url"], env_token or cached["token"]

    return env_url, env_token


def build_token_refresher(tenant_url: str) -> Callable[[], str] | None:
    """Return a zero-arg callable that mints a fresh token, or None.

    Looks for OAuth2 service-account credentials in two places, preferring
    the current environment (ephemeral, never touches disk) over the cache:

    1. ``IDIRA_IDENTITY_URL``/``IDIRA_ADMIN_USER``/``IDIRA_ADMIN_PWD`` env
       vars — typical when the shell sourced the same script that originally
       produced ``SECAI_TOKEN`` (e.g. ``env-vars.sh``), even if that token
       has since expired.
    2. The credentials cached by ``secai-cli login`` when it performed the
       OAuth2 exchange (see ``save_credentials``). In this case the
       refreshed token is also written back to the cache so the next CLI
       invocation picks it up without needing to refresh again.

    Returns None when neither source has a complete identity_url/client_id/
    client_secret triple, i.e. automatic refresh isn't possible and a 401
    will surface as ``AuthenticationError`` for the caller to handle (e.g. by
    prompting the user to run ``secai-cli login`` again).
    """
    identity_url = os.environ.get("IDIRA_IDENTITY_URL")
    client_id = os.environ.get("IDIRA_ADMIN_USER")
    client_secret = os.environ.get("IDIRA_ADMIN_PWD")
    from_cache = False

    if not (identity_url and client_id and client_secret):
        cached = load_credentials()
        if (
            cached
            and cached.get("identity_url")
            and cached.get("client_id")
            and cached.get("client_secret")
        ):
            identity_url = cached["identity_url"]
            client_id = cached["client_id"]
            client_secret = cached["client_secret"]
            from_cache = True
        else:
            return None

    def _refresh() -> str:
        new_token = fetch_access_token(identity_url, client_id, client_secret)
        if from_cache:
            save_credentials(
                tenant_url,
                new_token,
                identity_url=identity_url,
                client_id=client_id,
                client_secret=client_secret,
            )
        return new_token

    return _refresh
