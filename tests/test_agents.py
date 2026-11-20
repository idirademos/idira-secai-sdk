"""Unit tests for ``secai.agents.AgentsResource`` methods called directly via
``SecAIClient`` (not through the CLI).

Like ``test_pagination.py``, these tests run fully offline against a mocked
HTTP transport (``pytest-httpx``) — no live tenant required. ``list()`` and
``iter_all()`` are already covered in ``tests/test_pagination.py``; this file
focuses on the remaining ``AgentsResource`` methods.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from secai.client import SecAIClient
from secai.exceptions import ConflictError, NotFoundError
from secai.models import (
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


def _client() -> SecAIClient:
    return SecAIClient(tenant_url="https://tenant.example.com", token="test-token")


class TestAgentsSearch:
    def test_search_returns_list_agents_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/search",
            method="POST",
            json={
                "agents": [
                    {
                        "id": "agent-1",
                        "name": "My Agent",
                        "type": "AWS_BEDROCK",
                    }
                ],
                "pageInfo": {"continuationToken": None},
                "totalCount": 1,
            },
        )

        client = _client()
        request = SearchAgentsRequest(filter="type in [AWS_BEDROCK] and origin_id is null")
        result = client.agents.search(request)

        assert isinstance(result, ListAgentsResponse)
        assert result.total_count == 1
        assert len(result.agents) == 1
        assert result.agents[0].id == "agent-1"
        assert result.agents[0].name == "My Agent"

        sent_request = httpx_mock.get_requests()[0]
        assert sent_request.method == "POST"
        import json as _json

        assert _json.loads(sent_request.content) == {
            "filter": "type in [AWS_BEDROCK] and origin_id is null"
        }


class TestAgentsSummary:
    def test_summary_returns_agents_summary(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/summary",
            json={
                "types": {
                    "total": 3,
                    "items": [{"key": "AWS_BEDROCK", "displayText": "AWS Bedrock", "total": 3}],
                },
                "statuses": {
                    "total": 3,
                    "items": [{"key": "ACTIVE", "displayText": "Active", "total": 2}],
                },
                "spiffeCount": 1,
                "jwtCount": 2,
            },
        )

        client = _client()
        summary = client.agents.summary()

        assert isinstance(summary, AgentsSummary)
        assert summary.spiffe_count == 1
        assert summary.jwt_count == 2
        assert summary.types is not None
        assert summary.types.total == 3
        assert summary.statuses is not None
        assert summary.statuses.items[0].key == "ACTIVE"


class TestAgentsRegister:
    def test_register_returns_agent_with_credentials(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents",
            method="POST",
            json={
                "id": "agent-123",
                "name": "My Agent",
                "type": "CUSTOM",
                "description": "A test agent",
                "owner": "jdoe",
                "tags": {"env": "prod"},
                "credentials": {
                    "clientId": "client-abc",
                    "clientSecret": "secret-xyz",
                    "gatewayUrl": "https://gateway.example.com",
                },
            },
        )

        client = _client()
        request = RegisterAgentRequest(
            name="My Agent",
            type="CUSTOM",
            description="A test agent",
            owner="jdoe",
            tags={"env": "prod"},
        )
        agent = client.agents.register(request)

        assert isinstance(agent, AgentWithCredentials)
        assert agent.id == "agent-123"
        assert agent.name == "My Agent"
        assert agent.credentials is not None
        assert agent.credentials.client_id == "client-abc"
        assert agent.credentials.client_secret == "secret-xyz"
        assert agent.credentials.gateway_url == "https://gateway.example.com"


class TestAgentsGet:
    def test_get_returns_agent_with_credentials(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123",
            json={
                "id": "agent-123",
                "name": "My Agent",
                "type": "CUSTOM",
                "status": {"state": "ACTIVE"},
            },
        )

        client = _client()
        agent = client.agents.get("agent-123")

        assert isinstance(agent, AgentWithCredentials)
        assert agent.id == "agent-123"
        assert agent.name == "My Agent"
        assert agent.status is not None
        assert agent.status.state == AgentState.ACTIVE

    def test_get_raises_not_found_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/missing",
            status_code=404,
            json={"message": "Agent not found"},
        )

        client = _client()
        with pytest.raises(NotFoundError) as exc_info:
            client.agents.get("missing")

        assert exc_info.value.status_code == 404


class TestAgentsEdit:
    def test_edit_returns_updated_agent(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123",
            method="PUT",
            json={
                "id": "agent-123",
                "name": "Renamed Agent",
                "type": "CUSTOM",
                "description": "Updated description",
            },
        )

        client = _client()
        request = EditAgentRequest(name="Renamed Agent", description="Updated description")
        agent = client.agents.edit("agent-123", request)

        assert agent is not None
        assert agent.id == "agent-123"
        assert agent.name == "Renamed Agent"
        assert agent.description == "Updated description"

    def test_edit_returns_none_on_204(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123",
            method="PUT",
            status_code=204,
            content=b"",
        )

        client = _client()
        request = EditAgentRequest(name="Unchanged Name")
        result = client.agents.edit("agent-123", request)

        assert result is None


class TestAgentsDelete:
    def test_delete_returns_none(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123",
            method="DELETE",
            status_code=204,
            content=b"",
        )

        client = _client()
        result = client.agents.delete("agent-123")

        assert result is None
        sent_request = httpx_mock.get_requests()[0]
        assert sent_request.method == "DELETE"

    def test_delete_raises_conflict_error_when_active(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123",
            method="DELETE",
            status_code=409,
            json={"message": "Agent is ACTIVE and cannot be deleted"},
        )

        client = _client()
        with pytest.raises(ConflictError) as exc_info:
            client.agents.delete("agent-123")

        assert exc_info.value.status_code == 409


class TestAgentsSetState:
    def test_set_state_with_enum(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123/state",
            method="POST",
            json={"id": "agent-123", "status": {"state": "SUSPENDED"}},
        )

        client = _client()
        result = client.agents.set_state("agent-123", AgentState.SUSPENDED)

        assert isinstance(result, AgentStateResponse)
        assert result.id == "agent-123"
        assert result.status is not None
        assert result.status.state == AgentState.SUSPENDED

        import json as _json

        sent_request = httpx_mock.get_requests()[0]
        assert _json.loads(sent_request.content) == {"state": "SUSPENDED"}

    def test_set_state_with_plain_string(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123/state",
            method="POST",
            json={"id": "agent-123", "status": {"state": "ACTIVE"}},
        )

        client = _client()
        result = client.agents.set_state("agent-123", "ACTIVE")

        assert result.status is not None
        assert result.status.state == AgentState.ACTIVE


class TestAgentsAuthnDescriptors:
    def test_list_authn_descriptors(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents/agent-123/authn-descriptors",
            json=[
                {"id": "descriptor-1", "type": "jwt", "data": {"issuer": "https://issuer"}},
                {"id": "descriptor-2", "type": "oauth2", "data": {}},
            ],
        )

        client = _client()
        descriptors = client.agents.list_authn_descriptors("agent-123")

        assert len(descriptors) == 2
        assert all(isinstance(d, AuthnDescriptorOutput) for d in descriptors)
        assert descriptors[0].id == "descriptor-1"
        assert descriptors[0].type == "jwt"
        assert descriptors[0].data == {"issuer": "https://issuer"}
        assert descriptors[1].id == "descriptor-2"

    def test_delete_authn_descriptor_returns_none(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=(
                "https://tenant.example.com/api/agents/agent-123/"
                "authn-descriptors/descriptor-1"
            ),
            method="DELETE",
            status_code=204,
            content=b"",
        )

        client = _client()
        result = client.agents.delete_authn_descriptor("agent-123", "descriptor-1")

        assert result is None


class TestAgentsListSmoke:
    def test_list_returns_list_agents_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents",
            json={"agents": [{"id": "agent-1"}], "pageInfo": None, "totalCount": 1},
        )

        client = _client()
        result = client.agents.list()

        assert isinstance(result, ListAgentsResponse)
        assert result.agents[0].id == "agent-1"
