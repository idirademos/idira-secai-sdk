"""ReportsResource — methods for the /api/files/activity-map endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import ActivityMapReport

if TYPE_CHECKING:
    from .client import _BaseClient

_ACCEPT = "application/x.activity-map.beta+json"


class ReportsResource:
    """Provides access to the tenant's insights and activity map report."""

    def __init__(self, transport: _BaseClient) -> None:
        self._t = transport

    # ------------------------------------------------------------------
    # GET /api/files/activity-map
    # ------------------------------------------------------------------

    def get_activity_map(self, *, format: str | None = None) -> ActivityMapReport:
        """Return a short-lived presigned URL for the tenant's activity map report.

        *format* is ``"html"`` (default) or ``"json"``. The response does not
        contain the report content itself — issue a follow-up GET to
        ``download_url`` to retrieve the file; ``date_range`` describes the
        inclusive date range covered by the report.
        """
        params: dict[str, Any] = {}
        if format is not None:
            params["format"] = format
        body = self._t._request(
            "GET", "/api/files/activity-map", accept=_ACCEPT, params=params or None
        )
        return ActivityMapReport.model_validate(body)
