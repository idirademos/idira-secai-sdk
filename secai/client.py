"""SecAIClient — the primary entry point for the SecAI SDK."""

from __future__ import annotations

import hashlib
import os
import random
import sys
import time
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx

from .exceptions import raise_for_status

_AGENTS_ACCEPT = "application/x.agents.beta+json"
_TARGETS_ACCEPT = "application/x.targets.beta+json"

# Status codes that are safe to retry regardless of HTTP method: 429 means
# the request was rejected before being processed, and 502/503/504 are
# gateway-level failures where the request very likely never reached the
# application. Plain 500 is only retried for GET (see _request) since it may
# indicate a write was partially applied.
_RETRYABLE_STATUS = {429, 502, 503, 504}


class _BaseClient:
    """Shared HTTP transport used by resource classes."""

    def __init__(
        self,
        tenant_url: str,
        token: str,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 8.0,
        token_refresher: Callable[[], str] | None = None,
    ) -> None:
        # Strip trailing slash, then strip a trailing /api if present.
        # All resource paths already begin with /api/, so including it in
        # the tenant URL doubles the prefix and routes requests to the wrong
        # endpoint, producing a spurious "Invalid Authorization header" error.
        _base = tenant_url.rstrip("/")
        self._base_url = _base[:-4] if _base.endswith("/api") else _base
        self._token = token
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._max_backoff = max_backoff
        self._token_refresher = token_refresher
        self._http = httpx.Client(
            timeout=timeout,
            verify=verify_ssl,
        )

    @staticmethod
    def _mask_token(token: str) -> str:
        """Return a safe representation: first 8 chars + SHA-256 hash suffix."""
        if len(token) <= 8:
            return "***"
        h = hashlib.sha256(token.encode()).hexdigest()[:8]
        return f"{token[:8]}…[sha256:{h}]"

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter: backoff_factor * 2**attempt, capped."""
        base = self._backoff_factor * (2**attempt)
        return float(min(base, self._max_backoff)) + random.uniform(0, 0.25)

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Honor a Retry-After header (seconds or HTTP-date) if present."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                try:
                    dt = parsedate_to_datetime(retry_after)
                    return max((dt - dt.now(dt.tzinfo)).total_seconds(), 0.0)
                except (TypeError, ValueError):
                    pass
        return self._backoff_delay(attempt)

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a request and return the parsed JSON body (or None for 204).

        Transient failures are retried with exponential backoff:
        connection/timeout errors and 429/502/503/504 responses are retried
        regardless of HTTP method (the request is unlikely to have been
        processed); a plain 500 is only retried for GET, since POST/PUT/DELETE
        may have partially applied before the error. A 401 triggers a single
        silent token refresh (if a ``token_refresher`` was configured) before
        falling back to raising ``AuthenticationError``.
        """
        url = f"{self._base_url}{path}"
        _debug = os.environ.get("SECAI_DEBUG", "").lower() in ("1", "true", "yes")
        attempt = 0
        reauthenticated = False

        while True:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Accept": accept,
                "Content-Type": "application/json",
            }

            if _debug:
                masked = self._mask_token(self._token)
                print(
                    f"[DEBUG] {method} {url}\n"
                    f"[DEBUG] Authorization: Bearer {masked}\n"
                    f"[DEBUG] Accept: {accept}\n"
                    f"[DEBUG] Body: {json}",
                    file=sys.stderr,
                )

            try:
                response = self._http.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                )
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                if _debug:
                    print(
                        f"[DEBUG] Transport error ({exc}); retrying in "
                        f"{delay:.1f}s (attempt {attempt + 1}/{self._max_retries})",
                        file=sys.stderr,
                    )
                time.sleep(delay)
                attempt += 1
                continue

            if _debug:
                print(
                    f"[DEBUG] Response: HTTP {response.status_code}\n"
                    f"[DEBUG] Response body: {response.text[:500]}",
                    file=sys.stderr,
                )

            if response.status_code == 204:
                return None
            try:
                body: dict[str, Any] = response.json()
            except Exception:
                body = {}

            if response.is_success:
                return body

            refresher = self._token_refresher
            if response.status_code == 401 and refresher is not None and not reauthenticated:
                reauthenticated = True
                try:
                    self._token = refresher()
                except Exception as exc:
                    if _debug:
                        print(f"[DEBUG] Token refresh failed: {exc}", file=sys.stderr)
                    raise_for_status(response.status_code, body)
                else:
                    continue

            retryable = response.status_code in _RETRYABLE_STATUS or (
                response.status_code == 500 and method.upper() == "GET"
            )
            if retryable and attempt < self._max_retries:
                delay = self._retry_delay(response, attempt)
                if _debug:
                    print(
                        f"[DEBUG] HTTP {response.status_code}; retrying in "
                        f"{delay:.1f}s (attempt {attempt + 1}/{self._max_retries})",
                        file=sys.stderr,
                    )
                time.sleep(delay)
                attempt += 1
                continue

            raise_for_status(response.status_code, body)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> _BaseClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class SecAIClient:
    """Client for the CyberArk Secure AI API.

    Usage::

        client = SecAIClient(
            tenant_url="https://mytenant.cyberark.cloud",
            token="<bearer-jwt>",
        )
        agents = client.agents.list()

    Transient failures (connection errors, 429, 502/503/504, and 500 on GET
    requests) are retried automatically with exponential backoff — tune this
    with ``max_retries``/``backoff_factor``/``max_backoff`` or set
    ``max_retries=0`` to disable.

    Pass ``token_refresher`` — a zero-argument callable returning a fresh
    bearer token — to have the client silently re-authenticate and retry
    once when a request fails with HTTP 401, instead of raising
    ``AuthenticationError`` immediately.
    """

    def __init__(
        self,
        tenant_url: str | None = None,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 8.0,
        token_refresher: Callable[[], str] | None = None,
    ) -> None:
        resolved_url = tenant_url or os.environ.get("SECAI_TENANT_URL", "")
        resolved_token = token or os.environ.get("SECAI_TOKEN", "")

        if not resolved_url:
            raise ValueError("tenant_url must be provided or SECAI_TENANT_URL must be set.")
        if not resolved_token:
            raise ValueError("token must be provided or SECAI_TOKEN must be set.")

        self._transport = _BaseClient(
            resolved_url,
            resolved_token,
            timeout=timeout,
            verify_ssl=verify_ssl,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            max_backoff=max_backoff,
            token_refresher=token_refresher,
        )

        # Lazy-imported to avoid circular references
        from .agents import AgentsResource
        from .policies import PoliciesResource
        from .reports import ReportsResource
        from .targets import TargetsResource

        self.agents = AgentsResource(self._transport)
        self.targets = TargetsResource(self._transport)
        self.policies = PoliciesResource(self._transport)
        self.reports = ReportsResource(self._transport)

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> SecAIClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
