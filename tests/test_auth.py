"""Unit tests for secai-cli's local credential cache and login/logout/whoami.

Unlike the other test modules in this package, these tests do not require a
live tenant: the credential cache is pure local file I/O, and the OAuth2
client_credentials exchange / login validation call are mocked with
pytest-httpx so the suite can run offline and deterministically.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from secai.cli import auth
from secai.cli.main import app

runner = CliRunner()

# Captured before any test's autouse fixture monkeypatches `auth._import_keyring`,
# so the `SECAI_NO_KEYRING` opt-out test below can restore and exercise the real
# implementation rather than a stub that would trivially ignore the env var.
_real_import_keyring = auth._import_keyring


@pytest.fixture(autouse=True)
def isolated_credentials_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the credential cache at a throwaway path for every test.

    Also forces ``auth._import_keyring()`` to report "unavailable" by
    default. ``keyring`` is a required dependency, so without this, tests
    that don't care about the keyring backend would otherwise read from and
    write to the *real* OS keychain on a developer's machine (or on any CI
    runner where a Secret Service happens to be reachable) instead of the
    throwaway file above. Tests in ``TestKeyringBackend`` explicitly
    re-``monkeypatch`` ``_import_keyring`` with ``_FakeKeyringModule`` to
    opt back into exercising the keyring code path.
    """
    config_dir = tmp_path / "secai-config"
    credentials_file = config_dir / "credentials.json"
    monkeypatch.setattr(auth, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(auth, "_CREDENTIALS_FILE", credentials_file)
    monkeypatch.setattr(auth, "_import_keyring", lambda: None)
    # Ensure no ambient env vars leak into resolve_credentials()/login prompts.
    for var in (
        "SECAI_TENANT_URL",
        "SECAI_TOKEN",
        "IDIRA_IDENTITY_URL",
        "IDIRA_ADMIN_USER",
        "IDIRA_ADMIN_PWD",
    ):
        monkeypatch.delenv(var, raising=False)
    return credentials_file


# ---------------------------------------------------------------------------
# Local credential cache (save/load/clear/resolve)
# ---------------------------------------------------------------------------


class TestCredentialCache:
    def test_load_returns_none_when_absent(self) -> None:
        assert auth.load_credentials() is None

    def test_save_then_load_round_trips(self) -> None:
        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        assert auth.load_credentials() == {
            "tenant_url": "https://example.cyberark.cloud",
            "token": "tok-123",
        }

    def test_save_sets_owner_only_permissions(self, isolated_credentials_file: Path) -> None:
        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        mode = stat.S_IMODE(isolated_credentials_file.stat().st_mode)
        assert mode == stat.S_IRUSR | stat.S_IWUSR

    def test_clear_removes_existing_file(self) -> None:
        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        assert auth.clear_credentials() is True
        assert auth.load_credentials() is None

    def test_clear_is_a_noop_when_nothing_cached(self) -> None:
        assert auth.clear_credentials() is False

    def test_load_ignores_malformed_json(self, isolated_credentials_file: Path) -> None:
        isolated_credentials_file.parent.mkdir(parents=True, exist_ok=True)
        isolated_credentials_file.write_text("not json")
        assert auth.load_credentials() is None

    def test_load_ignores_missing_keys(self, isolated_credentials_file: Path) -> None:
        isolated_credentials_file.parent.mkdir(parents=True, exist_ok=True)
        isolated_credentials_file.write_text(json.dumps({"tenant_url": "https://x"}))
        assert auth.load_credentials() is None

    def test_save_with_oauth_identity_round_trips(self) -> None:
        auth.save_credentials(
            "https://example.cyberark.cloud",
            "tok-123",
            identity_url="https://identity.example.com",
            client_id="my-client",
            client_secret="my-secret",
        )
        assert auth.load_credentials() == {
            "tenant_url": "https://example.cyberark.cloud",
            "token": "tok-123",
            "identity_url": "https://identity.example.com",
            "client_id": "my-client",
            "client_secret": "my-secret",
        }

    def test_save_without_oauth_identity_omits_those_keys(self) -> None:
        """A direct --token login must not add partial/empty identity fields."""
        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        cached = auth.load_credentials()
        assert cached is not None
        assert "identity_url" not in cached
        assert "client_id" not in cached
        assert "client_secret" not in cached


class _FakeKeyringModule:
    """Stand-in for the `keyring` module, used to test backend selection
    deterministically without depending on a real OS keychain being present
    or usable on the machine running the test suite."""

    def __init__(self, *, usable: bool = True, backend_name: str = "FakeMacOSKeychain") -> None:
        self.usable = usable
        self.backend_name = backend_name
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        if not self.usable:
            raise RuntimeError("fake: no keyring backend available")
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if not self.usable:
            raise RuntimeError("fake: no keyring backend available")
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if not self.usable:
            raise RuntimeError("fake: no keyring backend available")
        key = (service, username)
        if key not in self.store:
            raise RuntimeError("fake: no matching entry")
        del self.store[key]

    def get_keyring(self) -> Any:
        return type(self.backend_name, (), {})()


class TestKeyringBackend:
    """Covers the OS-keyring storage backend (`keyring` package, a required
    dependency, but whose actual *usability* still varies by platform/session).

    These tests never touch the real OS keychain — the `isolated_credentials_file`
    autouse fixture stubs `auth._import_keyring` to `None` by default, and each
    test here re-patches it with `_FakeKeyringModule` to simulate "available and
    working" (e.g. macOS/Windows) vs. "installed but unusable" (e.g. headless
    Linux with no Secret Service daemon) states.
    """

    def test_active_backend_is_file_when_keyring_not_installed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auth, "_import_keyring", lambda: None)
        assert "plaintext file" in auth.active_backend()

    def test_save_and_load_use_keyring_when_available(
        self, monkeypatch: pytest.MonkeyPatch, isolated_credentials_file: Path
    ) -> None:
        fake = _FakeKeyringModule()
        monkeypatch.setattr(auth, "_import_keyring", lambda: fake)

        auth.save_credentials("https://example.cyberark.cloud", "tok-123")

        assert auth.load_credentials() == {
            "tenant_url": "https://example.cyberark.cloud",
            "token": "tok-123",
        }
        assert not isolated_credentials_file.exists()
        assert auth.active_backend() == "OS keyring (FakeMacOSKeychain)"

    def test_falls_back_to_file_when_keyring_unusable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        isolated_credentials_file: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake = _FakeKeyringModule(usable=False)
        monkeypatch.setattr(auth, "_import_keyring", lambda: fake)

        auth.save_credentials("https://example.cyberark.cloud", "tok-123")

        assert isolated_credentials_file.exists()
        assert auth.load_credentials() == {
            "tenant_url": "https://example.cyberark.cloud",
            "token": "tok-123",
        }
        assert "keyring unavailable" in capsys.readouterr().err

    def test_clear_removes_from_both_keyring_and_file(
        self, monkeypatch: pytest.MonkeyPatch, isolated_credentials_file: Path
    ) -> None:
        fake = _FakeKeyringModule()
        monkeypatch.setattr(auth, "_import_keyring", lambda: fake)

        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        assert auth.clear_credentials() is True
        assert auth.load_credentials() is None
        assert fake.store == {}

    def test_opportunistic_migration_from_file_to_keyring(
        self, monkeypatch: pytest.MonkeyPatch, isolated_credentials_file: Path
    ) -> None:
        """A pre-existing plaintext cache is moved into the keyring on next load."""
        auth.save_credentials("https://example.cyberark.cloud", "tok-123")
        assert isolated_credentials_file.exists()

        fake = _FakeKeyringModule()
        monkeypatch.setattr(auth, "_import_keyring", lambda: fake)

        assert auth.load_credentials() == {
            "tenant_url": "https://example.cyberark.cloud",
            "token": "tok-123",
        }
        assert not isolated_credentials_file.exists()
        assert fake.store

    def test_no_keyring_env_var_forces_file_even_if_keyring_works(
        self, monkeypatch: pytest.MonkeyPatch, isolated_credentials_file: Path
    ) -> None:
        """``SECAI_NO_KEYRING`` must short-circuit before any import/probe.

        This exercises the *real* ``_import_keyring()`` (restored here,
        since the ``isolated_credentials_file`` fixture stubs it to ``None``
        by default) with a working fake ``keyring`` module installed in
        ``sys.modules``, so a true "keyring would otherwise work" scenario
        is being opted out of — not just a stub that ignores the env var.
        """
        fake = _FakeKeyringModule()
        monkeypatch.setitem(sys.modules, "keyring", fake)
        monkeypatch.setattr(auth, "_import_keyring", _real_import_keyring)
        monkeypatch.setattr(auth, "_keyring_module_cache", auth._NOT_LOADED)
        monkeypatch.setenv("SECAI_NO_KEYRING", "1")

        auth.save_credentials("https://example.cyberark.cloud", "tok-123")

        assert fake.store == {}
        assert isolated_credentials_file.exists()


class TestResolveCredentials:
    def test_env_vars_used_when_no_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECAI_TENANT_URL", "https://env.example.com")
        monkeypatch.setenv("SECAI_TOKEN", "env-token")
        assert auth.resolve_credentials() == ("https://env.example.com", "env-token")

    def test_cache_used_when_no_env_vars(self) -> None:
        auth.save_credentials("https://cached.example.com", "cached-token")
        assert auth.resolve_credentials() == ("https://cached.example.com", "cached-token")

    def test_env_vars_take_precedence_over_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        auth.save_credentials("https://cached.example.com", "cached-token")
        monkeypatch.setenv("SECAI_TENANT_URL", "https://env.example.com")
        monkeypatch.setenv("SECAI_TOKEN", "env-token")
        assert auth.resolve_credentials() == ("https://env.example.com", "env-token")

    def test_nothing_available_returns_none_none(self) -> None:
        assert auth.resolve_credentials() == (None, None)


class TestBuildTokenRefresher:
    def test_returns_none_when_nothing_available(self) -> None:
        assert auth.build_token_refresher("https://tenant.example.com") is None

    def test_returns_none_when_identity_triple_incomplete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("IDIRA_IDENTITY_URL", "https://identity.example.com")
        monkeypatch.setenv("IDIRA_ADMIN_USER", "my-client")
        # IDIRA_ADMIN_PWD deliberately left unset.
        assert auth.build_token_refresher("https://tenant.example.com") is None

    def test_env_vars_used_when_present(
        self, monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
    ) -> None:
        monkeypatch.setenv("IDIRA_IDENTITY_URL", "https://identity.example.com")
        monkeypatch.setenv("IDIRA_ADMIN_USER", "my-client")
        monkeypatch.setenv("IDIRA_ADMIN_PWD", "my-secret")
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "fresh-token"},
        )

        refresher = auth.build_token_refresher("https://tenant.example.com")
        assert refresher is not None
        assert refresher() == "fresh-token"
        # Env-sourced refreshes are ephemeral — nothing should be written to disk.
        assert auth.load_credentials() is None

    def test_cache_used_when_no_env_vars(self, httpx_mock: HTTPXMock) -> None:
        auth.save_credentials(
            "https://tenant.example.com",
            "stale-token",
            identity_url="https://identity.example.com",
            client_id="my-client",
            client_secret="my-secret",
        )
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "fresh-token"},
        )

        refresher = auth.build_token_refresher("https://tenant.example.com")
        assert refresher is not None
        assert refresher() == "fresh-token"
        # Cache-sourced refreshes persist the new token for future invocations.
        assert auth.load_credentials() == {
            "tenant_url": "https://tenant.example.com",
            "token": "fresh-token",
            "identity_url": "https://identity.example.com",
            "client_id": "my-client",
            "client_secret": "my-secret",
        }

    def test_returns_none_when_cache_has_no_oauth_identity(self) -> None:
        auth.save_credentials("https://tenant.example.com", "tok-123")
        assert auth.build_token_refresher("https://tenant.example.com") is None

    def test_env_vars_take_precedence_over_cache(
        self, monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
    ) -> None:
        auth.save_credentials(
            "https://tenant.example.com",
            "stale-token",
            identity_url="https://cached-identity.example.com",
            client_id="cached-client",
            client_secret="cached-secret",
        )
        monkeypatch.setenv("IDIRA_IDENTITY_URL", "https://env-identity.example.com")
        monkeypatch.setenv("IDIRA_ADMIN_USER", "env-client")
        monkeypatch.setenv("IDIRA_ADMIN_PWD", "env-secret")
        httpx_mock.add_response(
            url="https://env-identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "env-fresh-token"},
        )

        refresher = auth.build_token_refresher("https://tenant.example.com")
        assert refresher is not None
        assert refresher() == "env-fresh-token"
        # The env path never touches the cache, so the stale cached token remains.
        assert auth.load_credentials() == {
            "tenant_url": "https://tenant.example.com",
            "token": "stale-token",
            "identity_url": "https://cached-identity.example.com",
            "client_id": "cached-client",
            "client_secret": "cached-secret",
        }


# ---------------------------------------------------------------------------
# OAuth2 client_credentials token exchange
# ---------------------------------------------------------------------------


class TestFetchAccessToken:
    def test_success_returns_access_token(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "issued-token-abc"},
        )
        token = auth.fetch_access_token(
            "https://identity.example.com", "client-id", "client-secret"
        )
        assert token == "issued-token-abc"

    def test_strips_trailing_slash_from_identity_url(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "issued-token-abc"},
        )
        token = auth.fetch_access_token(
            "https://identity.example.com/", "client-id", "client-secret"
        )
        assert token == "issued-token-abc"

    def test_non_200_raises_token_fetch_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            status_code=401,
            json={"error": "invalid_client"},
        )
        with pytest.raises(auth.TokenFetchError, match="authentication failed"):
            auth.fetch_access_token("https://identity.example.com", "bad-id", "bad-secret")

    def test_missing_access_token_field_raises(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"unexpected": "shape"},
        )
        with pytest.raises(auth.TokenFetchError, match="missing access_token"):
            auth.fetch_access_token("https://identity.example.com", "client-id", "client-secret")

    def test_connection_error_raises_token_fetch_error(self, httpx_mock: HTTPXMock) -> None:
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("boom"))
        with pytest.raises(auth.TokenFetchError, match="could not reach"):
            auth.fetch_access_token("https://unreachable.example.com", "client-id", "secret")


# ---------------------------------------------------------------------------
# `secai-cli login` / `logout` / `whoami`
# ---------------------------------------------------------------------------


class TestLoginCommand:
    def test_direct_token_skips_oauth_exchange(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents?pageSize=1",
            json={"agents": [], "pageInfo": {}, "totalCount": 0},
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--tenant-url",
                "https://tenant.example.com",
                "--token",
                "my-raw-token",
            ],
        )
        assert result.exit_code == 0, result.output
        assert auth.load_credentials() == {
            "tenant_url": "https://tenant.example.com",
            "token": "my-raw-token",
        }

    def test_oauth_exchange_used_when_no_token_given(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            json={"access_token": "oauth-issued-token"},
        )
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents?pageSize=1",
            json={"agents": [], "pageInfo": {}, "totalCount": 0},
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--tenant-url",
                "https://tenant.example.com",
                "--identity-url",
                "https://identity.example.com",
                "--client-id",
                "my-client",
                "--client-secret",
                "my-secret",
            ],
        )
        assert result.exit_code == 0, result.output
        assert auth.load_credentials() == {
            "tenant_url": "https://tenant.example.com",
            "token": "oauth-issued-token",
            "identity_url": "https://identity.example.com",
            "client_id": "my-client",
            "client_secret": "my-secret",
        }

    def test_failed_oauth_exchange_does_not_cache_anything(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://identity.example.com/oauth2/platformtoken",
            method="POST",
            status_code=401,
            json={"error": "invalid_client"},
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--tenant-url",
                "https://tenant.example.com",
                "--identity-url",
                "https://identity.example.com",
                "--client-id",
                "my-client",
                "--client-secret",
                "wrong-secret",
            ],
        )
        assert result.exit_code != 0
        assert auth.load_credentials() is None

    def test_failed_validation_call_does_not_cache_anything(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents?pageSize=1",
            status_code=401,
            json={"message": "invalid token"},
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--tenant-url",
                "https://tenant.example.com",
                "--token",
                "a-bad-token",
            ],
        )
        assert result.exit_code != 0
        assert auth.load_credentials() is None


class TestLogoutCommand:
    def test_logout_removes_cached_credentials(self) -> None:
        auth.save_credentials("https://tenant.example.com", "tok")
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert auth.load_credentials() is None

    def test_logout_when_not_logged_in_still_exits_zero(self) -> None:
        result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0


class TestWhoamiCommand:
    def test_whoami_before_login_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code != 0
        assert "Not logged in" in result.output

    def test_whoami_after_login_shows_masked_token(self) -> None:
        auth.save_credentials("https://tenant.example.com", "abcdefgh12345678")
        result = runner.invoke(app, ["whoami"])
        assert result.exit_code == 0
        assert "https://tenant.example.com" in result.output
        assert "abcdefgh12345678" not in result.output
