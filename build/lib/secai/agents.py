"""AgentsResource — methods for the /api/agents endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import (
    Agent,
    AgentState,
    AgentStateResponse,
    AgentWithCredentials,
    EditAgentRequest,
    ListAgentsResponse,
    RegisterAgentRequest,
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

    def list(self) -> list[Agent]:
        """Return all agents in the tenant."""
        body = self._t._request("GET", "/api/agents", accept=_ACCEPT)
        return ListAgentsResponse.model_validate(body).agents

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
    # PATCH /api/agents/{agentId}
    # ------------------------------------------------------------------

    def edit(self, agent_id: str, request: EditAgentRequest) -> Agent:
        """Edit agent metadata (name, owner, description, tags).

        Fields not included in *request* are left unchanged.
        """
        body = self._t._request(
            "PUT",
            f"/api/agents/{agent_id}",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return Agent.model_validate(body)

    # ------------------------------------------------------------------
    # DELETE /api/agents/{agentId}
    # ------------------------------------------------------------------

    def delete(self, agent_id: str) -> None:
        """Permanently delete an agent.

        The agent must be in ``SUSPENDED`` or ``PENDING_CONFIGURATION`` state.
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
