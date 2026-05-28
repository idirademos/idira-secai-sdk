"""SecAIClient — the primary entry point for the SecAI SDK."""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Any, Optional

import httpx

from .exceptions import raise_for_status

_AGENTS_ACCEPT = "application/x.agents.beta+json"
_TARGETS_ACCEPT = "application/x.targets.beta+json"


class _BaseClient:
    """Shared HTTP transport used by resource classes."""

    def __init__(
        self,
        tenant_url: str,
        token: str,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        # Strip trailing slash, then strip a trailing /api if present.
        # All resource paths already begin with /api/, so including it in
        # the tenant URL doubles the prefix and routes requests to the wrong
        # endpoint, producing a spurious "Invalid Authorization header" error.
        _base = tenant_url.rstrip("/")
        self._base_url = _base[:-4] if _base.endswith("/api") else _base
        self._token = token
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        accept: str,
        json: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Execute a request and return the parsed JSON body (or None for 204)."""
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept,
            "Content-Type": "application/json",
        }

        _debug = os.environ.get("SECAI_DEBUG", "").lower() in ("1", "true", "yes")
        if _debug:
            masked = self._mask_token(self._token)
            print(
                f"[DEBUG] {method} {url}\n"
                f"[DEBUG] Authorization: Bearer {masked}\n"
                f"[DEBUG] Accept: {accept}\n"
                f"[DEBUG] Body: {json}",
                file=sys.stderr,
            )

        response = self._http.request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
        )

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
        if not response.is_success:
            raise_for_status(response.status_code, body)
        return body

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "_BaseClient":
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
    """

    def __init__(
        self,
        tenant_url: Optional[str] = None,
        token: Optional[str] = None,
        *,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        resolved_url = tenant_url or os.environ.get("SECAI_TENANT_URL", "")
        resolved_token = token or os.environ.get("SECAI_TOKEN", "")

        if not resolved_url:
            raise ValueError(
                "tenant_url must be provided or SECAI_TENANT_URL must be set."
            )
        if not resolved_token:
            raise ValueError(
                "token must be provided or SECAI_TOKEN must be set."
            )

        self._transport = _BaseClient(
            resolved_url,
            resolved_token,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )

        # Lazy-imported to avoid circular references
        from .agents import AgentsResource
        from .targets import TargetsResource

        self.agents = AgentsResource(self._transport)
        self.targets = TargetsResource(self._transport)

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._transport.close()

    def __enter__(self) -> "SecAIClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
