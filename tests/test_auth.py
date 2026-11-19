"""Unit tests for secai-cli's local credential cache and login/logout/whoami.

Unlike the other test modules in this package, these tests do not require a
live tenant: the credential cache is pure local file I/O, and the OAuth2
client_credentials exchange / login validation call are mocked with
pytest-httpx so the suite can run offline and deterministically.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from secai.cli import auth
from secai.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_credentials_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the credential cache at a throwaway path for every test."""
    config_dir = tmp_path / "secai-config"
    credentials_file = config_dir / "credentials.json"
    monkeypatch.setattr(auth, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(auth, "_CREDENTIALS_FILE", credentials_file)
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
