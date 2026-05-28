"""Exception hierarchy for the SecAI SDK."""

from __future__ import annotations


class SecAIError(Exception):
    """Base exception for all SecAI SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        description: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.description = description

    def __str__(self) -> str:
        parts = [self.message]
        if self.error_code:
            parts.insert(0, f"[{self.error_code}]")
        if self.description:
            parts.append(self.description)
        return " — ".join(parts)


class AuthenticationError(SecAIError):
    """HTTP 401 — missing or invalid bearer token."""


class AuthorizationError(SecAIError):
    """HTTP 403 — caller lacks permission for the requested operation."""


class NotFoundError(SecAIError):
    """HTTP 404 — the requested resource does not exist."""


class ConflictError(SecAIError):
    """HTTP 409 — duplicate name, or invalid lifecycle state transition."""


class ValidationError(SecAIError):
    """HTTP 422 — request body fails schema or business-rule validation."""


class RateLimitError(SecAIError):
    """HTTP 429 — too many requests; back off and retry."""


class ServerError(SecAIError):
    """HTTP 5xx — an unexpected error occurred on the server."""


class UnexpectedError(SecAIError):
    """Any other HTTP error not covered by a specific subclass."""


_STATUS_MAP: dict[int, type[SecAIError]] = {
    401: AuthenticationError,
    403: AuthorizationError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


_AIGW_AUTH_HINT = (
    "HTTP 403 — access denied for this operation. "
    "Possible causes: (1) the service account lacks the agent-edit role in "
    "CyberArk Identity; (2) you are not the agent owner and do not hold the "
    "AIGW admin role; (3) the OAuth2 token was issued from the idadmin "
    "endpoint — try the portal-ID endpoint "
    "(https://<portal-id>.id.cyberark.cloud/oauth2/platformtoken) which "
    "includes the audience claim required for write operations."
)


def raise_for_status(status_code: int, body: dict[str, object]) -> None:
    """Raise the appropriate SecAIError for a non-2xx response."""
    message = str(body.get("message", f"HTTP {status_code}"))
    error_code = str(body.get("code", ""))
    description = str(body.get("description", "")) if body.get("description") else None

    if status_code >= 500:
        raise ServerError(
            message,
            status_code=status_code,
            error_code=error_code or None,
            description=description,
        )

    # The AIGW returns a generic "Invalid key=value pair (missing equal-sign)
    # in Authorization header" message for ALL 403 scenarios (wrong scope, not
    # the resource owner, missing admin role).  Surface a clearer hint instead.
    if status_code == 403 and "missing equal-sign" in message.lower():
        raise AuthorizationError(
            _AIGW_AUTH_HINT,
            status_code=403,
            error_code=error_code or None,
            description=message,  # preserve the raw AIGW message as description
        )

    exc_class = _STATUS_MAP.get(status_code, UnexpectedError)
    raise exc_class(
        message,
        status_code=status_code,
        error_code=error_code or None,
        description=description,
    )
