"""AgentsResource — methods for the /api/agents endpoints."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any, Iterator, Optional

from .models import (
    Agent,
    AgentsSummary,
    AgentState,
    AgentStateResponse,
    AgentWithCredentials,
    AuthnDescriptorOutput,
    EditAgentRequest,
    ListAgentsResponse,
    RegisterAgentRequest,
    SearchAgentsRequest,
)

if TYPE_CHECKING:
    from .client import _BaseClient

_ACCEPT = "application/x.agents.beta+json"


class AgentsResource:
    """Provides access to all Agents API operations."""

    def __init__(self, transport: "_BaseClient") -> None:
        self._t = transport

    # ------------------------------------------------------------------
    # GET /api/agents
    # ------------------------------------------------------------------

    def list(
        self,
        *,
        page_size: Optional[int] = None,
        continuation_token: Optional[str] = None,
    ) -> ListAgentsResponse:
        """Return a page of agents in the tenant.

        *page_size* (1-1000) and *continuation_token* (from a previous
        response's ``page_info.continuation_token``) support cursor-based
        pagination. Returns the full :class:`~secai.models.ListAgentsResponse`
        (``agents``, ``page_info``, ``total_count``) so callers can fetch
        subsequent pages.
        """
        params: dict[str, Any] = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if continuation_token is not None:
            params["continuationToken"] = continuation_token
        body = self._t._request(
            "GET", "/api/agents", accept=_ACCEPT, params=params or None
        )
        return ListAgentsResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/agents (pagination helper)
    # ------------------------------------------------------------------

    def iter_all(self, *, page_size: Optional[int] = None) -> Iterator[Agent]:
        """Yield every agent in the tenant, transparently paging through results.

        Equivalent to repeatedly calling :meth:`list` and following
        ``page_info.continuation_token`` until the server stops returning one.
        """
        continuation_token: Optional[str] = None
        while True:
            page = self.list(page_size=page_size, continuation_token=continuation_token)
            yield from page.agents
            continuation_token = page.page_info.continuation_token if page.page_info else None
            if not continuation_token or not page.agents:
                return

    # ------------------------------------------------------------------
    # POST /api/agents/search
    # ------------------------------------------------------------------

    def search(self, request: SearchAgentsRequest) -> ListAgentsResponse:
        """Search agents with a filter expression.

        Supported filter fields are ``id``, ``type``, ``origin_id``, and
        ``spiffeId``, e.g. ``"type in [AWS_BEDROCK] and origin_id is null"``.
        """
        body = self._t._request(
            "POST",
            "/api/agents/search",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return ListAgentsResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/agents/summary
    # ------------------------------------------------------------------

    def summary(self) -> AgentsSummary:
        """Return counts of agents by type and connection status, plus SPIFFE/JWT counts."""
        body = self._t._request("GET", "/api/agents/summary", accept=_ACCEPT)
        return AgentsSummary.model_validate(body)

    # ------------------------------------------------------------------
    # POST /api/agents
    # ------------------------------------------------------------------

    def register(self, request: RegisterAgentRequest) -> AgentWithCredentials:
        """Register a new AI agent.

        Returns the agent record including the one-time ``credentials``
        (clientId, clientSecret, gatewayUrl).
        """
        body = self._t._request(
            "POST",
            "/api/agents",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return AgentWithCredentials.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/agents/{agentId}
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentWithCredentials:
        """Retrieve full details for a single agent."""
        body = self._t._request("GET", f"/api/agents/{agent_id}", accept=_ACCEPT)
        return AgentWithCredentials.model_validate(body)

    # ------------------------------------------------------------------
    # PUT /api/agents/{agentId}
    # ------------------------------------------------------------------

    def edit(self, agent_id: str, request: EditAgentRequest) -> Optional[Agent]:
        """Edit agent metadata (name, owners, description, tags, authnDescriptors).

        Fields not included in *request* are left unchanged. Returns ``None``
        if the request matches the stored agent exactly (HTTP 204: nothing is
        written or audited).
        """
        body = self._t._request(
            "PUT",
            f"/api/agents/{agent_id}",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return Agent.model_validate(body) if body is not None else None

    # ------------------------------------------------------------------
    # DELETE /api/agents/{agentId}
    # ------------------------------------------------------------------

    def delete(self, agent_id: str) -> None:
        """Permanently delete an agent.

        The agent must be in ``SUSPENDED`` or ``PENDING_CONNECTION`` state.
        Raises :class:`~secai.exceptions.ConflictError` if the agent is
        ``ACTIVE``.
        """
        self._t._request("DELETE", f"/api/agents/{agent_id}", accept=_ACCEPT)

    # ------------------------------------------------------------------
    # POST /api/agents/{agentId}/state
    # ------------------------------------------------------------------

    def set_state(self, agent_id: str, state: AgentState | str) -> AgentStateResponse:
        """Transition an agent between ``ACTIVE`` and ``SUSPENDED``.

        *state* should be ``"ACTIVE"`` or ``"SUSPENDED"`` (or the
        :class:`~secai.models.AgentState` enum).
        """
        payload: dict[str, Any] = {"state": AgentState(state).value}
        body = self._t._request(
            "POST",
            f"/api/agents/{agent_id}/state",
            accept=_ACCEPT,
            json=payload,
        )
        return AgentStateResponse.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/agents/{agentId}/authn-descriptors
    # ------------------------------------------------------------------

    def list_authn_descriptors(self, agent_id: str) -> builtins.list[AuthnDescriptorOutput]:
        """List all authentication descriptors registered for an agent.

        ``builtins.list`` is used here (rather than the bare ``list[...]``
        generic) because this class defines its own ``list()`` method, which
        would otherwise shadow the builtin in this annotation's lazy
        evaluation scope.
        """
        body = self._t._request(
            "GET", f"/api/agents/{agent_id}/authn-descriptors", accept=_ACCEPT
        )
        return [AuthnDescriptorOutput.model_validate(item) for item in body]

    # ------------------------------------------------------------------
    # DELETE /api/agents/{agentId}/authn-descriptors/{descriptorId}
    # ------------------------------------------------------------------

    def delete_authn_descriptor(self, agent_id: str, descriptor_id: str) -> None:
        """Remove a single authentication descriptor from an agent by its UUID.

        Adding descriptors via this resource is deprecated server-side; use
        ``register()``'s or ``edit()``'s ``authn_descriptors`` field instead.
        """
        self._t._request(
            "DELETE",
            f"/api/agents/{agent_id}/authn-descriptors/{descriptor_id}",
            accept=_ACCEPT,
        )
