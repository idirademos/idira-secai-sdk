"""Unit tests for SecAIClient's retry/backoff and 401 auto-refresh behavior.

Like ``test_auth.py``, these tests run fully offline against a mocked HTTP
transport (``pytest-httpx``) — no live tenant required. ``time.sleep`` is
monkeypatched to a no-op so backoff delays don't slow the suite down.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from secai.client import _BaseClient
from secai.exceptions import AuthenticationError, NotFoundError, RateLimitError, ServerError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip real backoff delays so these tests run instantly."""
    monkeypatch.setattr("secai.client.time.sleep", lambda _seconds: None)


def _client(**kwargs: Any) -> _BaseClient:
    kwargs.setdefault("max_retries", 2)
    kwargs.setdefault("backoff_factor", 0.01)
    kwargs.setdefault("max_backoff", 0.02)
    return _BaseClient("https://tenant.example.com", "initial-token", **kwargs)


# ---------------------------------------------------------------------------
# Retry on transient failures
# ---------------------------------------------------------------------------


class TestRetryBehavior:
    def test_retries_on_429_then_succeeds(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
        httpx_mock.add_response(status_code=200, json={"ok": True})

        client = _client()
        body = client._request("GET", "/api/agents", accept="application/json")
        assert body == {"ok": True}

    def test_retries_on_503_then_succeeds(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=503)
        httpx_mock.add_response(status_code=200, json={"ok": True})

        client = _client()
        body = client._request("GET", "/api/agents", accept="application/json")
        assert body == {"ok": True}

    def test_retries_on_502_for_post(self, httpx_mock: HTTPXMock) -> None:
        """502/503/504 are retried for any method, including POST."""
        httpx_mock.add_response(status_code=502)
        httpx_mock.add_response(status_code=201, json={"id": "abc"})

        client = _client()
        body = client._request("POST", "/api/agents", accept="application/json", json={})
        assert body == {"id": "abc"}

    def test_exhausts_retries_and_raises(self, httpx_mock: HTTPXMock) -> None:
        """max_retries=2 allows 2 retries (3 total attempts); a 4th 503 is never requested."""
        for _ in range(3):
            httpx_mock.add_response(status_code=503)

        client = _client()
        with pytest.raises(ServerError):
            client._request("GET", "/api/agents", accept="application/json")

    def test_500_retried_for_get(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=500)
        httpx_mock.add_response(status_code=200, json={"ok": True})

        client = _client()
        body = client._request("GET", "/api/agents", accept="application/json")
        assert body == {"ok": True}

    def test_500_not_retried_for_post(self, httpx_mock: HTTPXMock) -> None:
        """A plain 500 on a write is NOT retried (may have partially applied)."""
        httpx_mock.add_response(status_code=500, json={"message": "boom"})

        client = _client()
        with pytest.raises(ServerError):
            client._request("POST", "/api/agents", accept="application/json", json={})

    def test_404_is_not_retried(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404, json={"message": "not found"})

        client = _client()
        with pytest.raises(NotFoundError):
            client._request("GET", "/api/agents/missing", accept="application/json")

    def test_retry_after_header_honored_as_seconds(self, httpx_mock: HTTPXMock) -> None:
        """A numeric Retry-After should be used instead of exponential backoff."""
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "5"})
        httpx_mock.add_response(status_code=200, json={"ok": True})

        client = _client()
        body = client._request("GET", "/api/agents", accept="application/json")
        assert body == {"ok": True}

    def test_max_retries_zero_disables_retries(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=503)

        client = _client(max_retries=0)
        with pytest.raises(ServerError):
            client._request("GET", "/api/agents", accept="application/json")

    def test_429_without_refresher_or_further_retries_raises_rate_limit(
        self, httpx_mock: HTTPXMock
    ) -> None:
        for _ in range(3):
            httpx_mock.add_response(status_code=429)

        client = _client()
        with pytest.raises(RateLimitError):
            client._request("GET", "/api/agents", accept="application/json")


# ---------------------------------------------------------------------------
# 401 auto-refresh
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    def test_401_triggers_refresh_and_retries_once(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, json={"message": "expired"})
        httpx_mock.add_response(status_code=200, json={"ok": True})

        calls = {"count": 0}

        def _refresh() -> str:
            calls["count"] += 1
            return "fresh-token"

        client = _client(token_refresher=_refresh)
        body = client._request("GET", "/api/agents", accept="application/json")
        assert body == {"ok": True}
        assert calls["count"] == 1
        assert client._token == "fresh-token"

    def test_401_without_refresher_raises_immediately(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, json={"message": "expired"})

        client = _client()
        with pytest.raises(AuthenticationError):
            client._request("GET", "/api/agents", accept="application/json")

    def test_401_persists_after_one_refresh_attempt(self, httpx_mock: HTTPXMock) -> None:
        """If the server still rejects the refreshed token, raise rather than loop forever."""
        httpx_mock.add_response(status_code=401, json={"message": "expired"})
        httpx_mock.add_response(status_code=401, json={"message": "still invalid"})

        client = _client(token_refresher=lambda: "still-bad-token")
        with pytest.raises(AuthenticationError):
            client._request("GET", "/api/agents", accept="application/json")

    def test_refresh_callback_failure_raises_authentication_error(
        self, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(status_code=401, json={"message": "expired"})

        def _broken_refresh() -> str:
            raise RuntimeError("could not reach identity provider")

        client = _client(token_refresher=_broken_refresh)
        with pytest.raises(AuthenticationError):
            client._request("GET", "/api/agents", accept="application/json")
