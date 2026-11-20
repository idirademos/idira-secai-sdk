"""TargetsResource — methods for the /api/targets endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from .models import (
    EditMcpServerRequest,
    McpServerListResponse,
    McpServerResponse,
    McpState,
    PredefinedMcpListResponse,
    PredefinedMcpTargetDetail,
    RegisterCustomMcpServerRequest,
    RegisterPredefinedMcpServerRequest,
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
        page_size: Optional[int] = None,
        next_cursor: Optional[str] = None,
    ) -> McpServerListResponse:
        """Return registered MCP servers (cursor-paginated).

        Pass the ``next_cursor`` from a previous response to fetch the next
        page. *page_size* controls the maximum number of items per page
        (server-side default applies when omitted).
        """
        params: dict[str, Any] = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if next_cursor:
            params["nextCursor"] = next_cursor
        body = self._t._request(
            "GET",
            "/api/targets/mcp-servers",
            accept=_ACCEPT,
            params=params or None,
        )
        return McpServerListResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/targets/mcp-servers (pagination helper)
    # ------------------------------------------------------------------

    def iter_all_mcp_servers(
        self, *, page_size: Optional[int] = None
    ) -> Iterator[McpServerResponse]:
        """Yield every registered MCP server, transparently paging through results.

        Equivalent to repeatedly calling :meth:`list_mcp_servers` and following
        ``next_cursor`` until the server stops returning one.
        """
        next_cursor: Optional[str] = None
        while True:
            page = self.list_mcp_servers(page_size=page_size, next_cursor=next_cursor)
            yield from page.mcp_servers
            next_cursor = page.next_cursor
            if not next_cursor or not page.mcp_servers:
                return

    # ------------------------------------------------------------------
    # POST /api/targets/mcp-servers
    # ------------------------------------------------------------------

    def register_mcp_server(
        self,
        request: Union[RegisterCustomMcpServerRequest, RegisterPredefinedMcpServerRequest],
    ) -> McpServerResponse:
        """Register a custom or predefined MCP server target.

        Pass a :class:`~secai.models.RegisterCustomMcpServerRequest` to
        register a CUSTOM target (``name``, ``description``, ``category``,
        and ``upstream`` are required) or a
        :class:`~secai.models.RegisterPredefinedMcpServerRequest` to
        instantiate a catalog template (``source.predefinedTargetId`` is
        required).
        """
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

        Editable fields: ``description``, ``owners``, ``tags``, ``category``
        (custom targets only), and ``auth_method`` (API_KEY/PAT targets only,
        to rotate ``headers``/``api_keys``). ``name`` and ``upstream`` are
        immutable after creation.
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

        The target must be in ``DISABLED`` state first; predefined MCP
        servers cannot be deleted. A
        :class:`~secai.exceptions.ConflictError` is raised if either rule is
        violated.
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

    def get_predefined_mcp_server(self, predefined_id: str) -> PredefinedMcpTargetDetail:
        """Get details of a specific predefined MCP server template, including its tools."""
        body = self._t._request(
            "GET",
            f"/api/targets/predefined/mcp-servers/{predefined_id}",
            accept=_ACCEPT,
        )
        return PredefinedMcpTargetDetail.model_validate(body)
