"""Local credential cache for ``secai-cli login``.

Stores the tenant URL and token in ``~/.config/secai/credentials.json``
(mode 0600) so users can authenticate once instead of exporting
``SECAI_TENANT_URL``/``SECAI_TOKEN`` for every shell session.

Precedence when resolving credentials for a command: explicit
``SECAI_TENANT_URL``/``SECAI_TOKEN`` environment variables always win (so CI
and scripted usage is unaffected); the cached login is used only as a
fallback when those env vars are unset.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Optional

import httpx

_CONFIG_DIR = Path(os.environ.get("SECAI_CONFIG_DIR", "~/.config/secai")).expanduser()
_CREDENTIALS_FILE = _CONFIG_DIR / "credentials.json"


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


def save_credentials(tenant_url: str, token: str) -> None:
    """Persist credentials to the local cache with owner-only permissions."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(
        json.dumps({"tenant_url": tenant_url, "token": token}, indent=2) + "\n"
    )
    _CREDENTIALS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def load_credentials() -> Optional[dict[str, str]]:
    """Load cached credentials, or None if no login has been saved."""
    if not _CREDENTIALS_FILE.exists():
        return None
    try:
        data = json.loads(_CREDENTIALS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or "tenant_url" not in data or "token" not in data:
        return None
    return {"tenant_url": data["tenant_url"], "token": data["token"]}


def clear_credentials() -> bool:
    """Remove the cached credentials file. Returns True if a file was removed."""
    if _CREDENTIALS_FILE.exists():
        _CREDENTIALS_FILE.unlink()
        return True
    return False


def resolve_credentials() -> tuple[Optional[str], Optional[str]]:
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
