"""TargetsResource — methods for the /api/targets endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from .models import (
    EditMcpServerRequest,
    McpServerListResponse,
    McpServerResponse,
    McpServerStateRequest,
    McpState,
    PredefinedMcpListResponse,
    PredefinedMcpTarget,
    RegisterMcpServerRequest,
)

if TYPE_CHECKING:
    from .client import _BaseClient

_ACCEPT = "application/x.targets.beta+json"


class TargetsResource:
    """Provides access to all Targets API operations."""

    def __init__(self, transport: "_BaseClient") -> None:
        self._t = transport

    # ------------------------------------------------------------------
    # GET /api/targets/mcp-servers
    # ------------------------------------------------------------------

    def list_mcp_servers(
        self,
        *,
        cursor: Optional[str] = None,
    ) -> McpServerListResponse:
        """Return registered MCP servers (cursor-paginated).

        Pass the ``next_cursor`` from a previous response as *cursor* to
        fetch the next page.
        """
        params: dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        body = self._t._request(
            "GET",
            "/api/targets/mcp-servers",
            accept=_ACCEPT,
            params=params or None,
        )
        return McpServerListResponse.model_validate(body)

    # ------------------------------------------------------------------
    # POST /api/targets/mcp-servers
    # ------------------------------------------------------------------

    def register_mcp_server(
        self, request: RegisterMcpServerRequest
    ) -> McpServerResponse:
        """Register a custom or predefined MCP server target."""
        body = self._t._request(
            "POST",
            "/api/targets/mcp-servers",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return McpServerResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/targets/mcp-servers/{Id}
    # ------------------------------------------------------------------

    def get_mcp_server(self, server_id: str) -> McpServerResponse:
        """Get details of a registered MCP server."""
        body = self._t._request(
            "GET", f"/api/targets/mcp-servers/{server_id}", accept=_ACCEPT
        )
        return McpServerResponse.model_validate(body)

    # ------------------------------------------------------------------
    # PUT /api/targets/mcp-servers/{Id}
    # ------------------------------------------------------------------

    def edit_mcp_server(
        self, server_id: str, request: EditMcpServerRequest
    ) -> McpServerResponse:
        """Update MCP server metadata.

        Editable fields: ``description``, ``owners``, ``tags``,
        ``category`` (custom targets only).  ``name``, ``authMethod``,
        and ``upstream`` are immutable after creation.
        """
        body = self._t._request(
            "PUT",
            f"/api/targets/mcp-servers/{server_id}",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return McpServerResponse.model_validate(body)

    # ------------------------------------------------------------------
    # DELETE /api/targets/mcp-servers/{Id}
    # ------------------------------------------------------------------

    def delete_mcp_server(self, server_id: str) -> None:
        """Delete a custom MCP server.

        Predefined MCP servers cannot be deleted; a
        :class:`~secai.exceptions.ConflictError` is raised if attempted.
        """
        self._t._request(
            "DELETE", f"/api/targets/mcp-servers/{server_id}", accept=_ACCEPT
        )

    # ------------------------------------------------------------------
    # POST /api/targets/mcp-servers/{Id}/state
    # ------------------------------------------------------------------

    def set_mcp_server_state(
        self, server_id: str, state: McpState | str
    ) -> McpServerResponse:
        """Toggle a registered MCP server between ``ENABLED`` and ``DISABLED``.

        The state endpoint returns ``{"id": ..., "status": {"state": ...}}``
        rather than the full server object.  A follow-up GET is performed so
        the returned ``McpServerResponse`` always contains the complete record
        with ``state`` at the top level.
        """
        payload: dict[str, Any] = {"state": McpState(state).value}
        self._t._request(
            "POST",
            f"/api/targets/mcp-servers/{server_id}/state",
            accept=_ACCEPT,
            json=payload,
        )
        return self.get_mcp_server(server_id)

    # ------------------------------------------------------------------
    # GET /api/targets/predefined/mcp-servers
    # ------------------------------------------------------------------

    def list_predefined_mcp_servers(self) -> PredefinedMcpListResponse:
        """List all predefined MCP server templates from the catalog."""
        body = self._t._request(
            "GET", "/api/targets/predefined/mcp-servers", accept=_ACCEPT
        )
        return PredefinedMcpListResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/targets/predefined/mcp-servers/{Id}
    # ------------------------------------------------------------------

    def get_predefined_mcp_server(self, predefined_id: str) -> PredefinedMcpTarget:
        """Get details of a specific predefined MCP server template."""
        body = self._t._request(
            "GET",
            f"/api/targets/predefined/mcp-servers/{predefined_id}",
            accept=_ACCEPT,
        )
        return PredefinedMcpTarget.model_validate(body)
