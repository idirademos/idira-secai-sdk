"""Unit tests for ``secai.targets.TargetsResource``.

Like ``test_pagination.py`` and ``test_client_resilience.py``, these tests
exercise the SDK directly (``client.targets.<method>(...)``) against a real
``SecAIClient`` instance, with all HTTP mocked offline via ``pytest-httpx``.
No CLI/Typer involvement — see ``tests/test_targets_cli.py`` for CLI-level
coverage of the same resource.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from secai.client import SecAIClient
from secai.exceptions import ConflictError, NotFoundError
from secai.models import (
    EditMcpServerRequest,
    McpCategory,
    McpServerResponse,
    McpSource,
    McpSourceType,
    McpUpstream,
    PredefinedMcpListResponse,
    PredefinedMcpTargetDetail,
    RegisterCustomMcpServerRequest,
    RegisterPredefinedMcpServerRequest,
)

_BASE = "https://tenant.example.com/api/targets"
_SERVER_ID = "11111111-1111-1111-1111-111111111111"
_PREDEFINED_ID = "22222222-2222-2222-2222-222222222222"


def _client() -> SecAIClient:
    return SecAIClient(tenant_url="https://tenant.example.com", token="test-token")


def _mcp_server(
    *,
    server_id: str = _SERVER_ID,
    name: str = "test-mcp-server",
    state: str = "ENABLED",
    description: str = "A test MCP server",
    category: str = "WEB_AND_BROWSER_AUTOMATION",
    tags: dict[str, str] | None = None,
    source: dict | None = None,
) -> dict:
    return {
        "id": server_id,
        "source": source or {"type": "CUSTOM"},
        "name": name,
        "description": description,
        "category": category,
        "gatewayUrl": "https://gateway.example.com/mcp/" + server_id,
        "callbackUrl": None,
        "upstream": {"url": "https://mcp.context7.com/mcp"},
        "authMethod": {"type": "NONE"},
        "owners": [],
        "tags": tags or {},
        "state": state,
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "createdBy": "tester",
        "updatedBy": "tester",
    }


def _predefined_target(predefined_id: str = _PREDEFINED_ID) -> dict:
    return {
        "id": predefined_id,
        "predefinedTargetVersion": 1,
        "name": "Context7",
        "iconId": "context7",
        "description": "Context7 predefined MCP server",
        "category": "DEVELOPER_TOOLS_AND_SOURCE_CONTROL",
        "upstream": {"url": "https://mcp.context7.com/mcp"},
        "authMethod": "NONE",
        "tags": {},
        "createdAt": "2024-01-01T00:00:00Z",
    }


def _predefined_detail(predefined_id: str = _PREDEFINED_ID) -> dict:
    return {
        **_predefined_target(predefined_id),
        "tools": [{"name": "search", "description": "Search the docs"}],
    }


class TestListMcpServersSmoke:
    """Minimal smoke test; full pagination coverage lives in test_pagination.py."""

    def test_list_returns_typed_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )

        client = _client()
        result = client.targets.list_mcp_servers()

        assert result.mcp_servers[0].id == _SERVER_ID
        assert result.next_cursor is None


class TestRegisterMcpServer:
    def test_register_custom_mcp_server(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(name="custom-server", description="My custom server"),
        )

        request = RegisterCustomMcpServerRequest(
            name="custom-server",
            description="My custom server",
            category=McpCategory.WEB_AND_BROWSER_AUTOMATION,
            upstream=McpUpstream(url="https://mcp.context7.com/mcp"),
        )
        client = _client()
        result = client.targets.register_mcp_server(request)

        assert isinstance(result, McpServerResponse)
        assert result.id == _SERVER_ID
        assert result.name == "custom-server"
        assert result.description == "My custom server"
        assert result.source is not None
        assert result.source.type == McpSourceType.CUSTOM

    def test_register_predefined_mcp_server(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(
                name="Context7",
                source={"type": "PREDEFINED", "predefinedTargetId": _PREDEFINED_ID},
            ),
        )

        request = RegisterPredefinedMcpServerRequest(
            source=McpSource(
                type=McpSourceType.PREDEFINED,
                predefined_target_id=_PREDEFINED_ID,
            ),
        )
        client = _client()
        result = client.targets.register_mcp_server(request)

        assert isinstance(result, McpServerResponse)
        assert result.id == _SERVER_ID
        assert result.name == "Context7"
        assert result.source is not None
        assert result.source.type == McpSourceType.PREDEFINED
        assert result.source.predefined_target_id == _PREDEFINED_ID


class TestGetMcpServer:
    def test_get_returns_typed_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(),
        )

        client = _client()
        result = client.targets.get_mcp_server(_SERVER_ID)

        assert isinstance(result, McpServerResponse)
        assert result.id == _SERVER_ID
        assert result.name == "test-mcp-server"
        assert result.state is not None
        assert result.state.value == "ENABLED"

    def test_get_raises_not_found_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            status_code=404,
            json={"message": "MCP server not found"},
        )

        client = _client()
        with pytest.raises(NotFoundError) as exc_info:
            client.targets.get_mcp_server(_SERVER_ID)

        assert exc_info.value.status_code == 404


class TestEditMcpServer:
    def test_edit_returns_updated_server(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(description="Updated description", tags={"env": "prod"}),
        )

        request = EditMcpServerRequest(description="Updated description", tags={"env": "prod"})
        client = _client()
        result = client.targets.edit_mcp_server(_SERVER_ID, request)

        assert isinstance(result, McpServerResponse)
        assert result.description == "Updated description"
        assert result.tags == {"env": "prod"}


class TestDeleteMcpServer:
    def test_delete_returns_none(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            status_code=204,
        )

        client = _client()
        result = client.targets.delete_mcp_server(_SERVER_ID)

        assert result is None

    def test_delete_raises_conflict_error_when_not_disabled(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            status_code=409,
            json={"message": "Target must be DISABLED before it can be deleted"},
        )

        client = _client()
        with pytest.raises(ConflictError) as exc_info:
            client.targets.delete_mcp_server(_SERVER_ID)

        assert exc_info.value.status_code == 409


class TestSetMcpServerState:
    def test_set_state_performs_post_then_get(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}/state",
            json={"id": _SERVER_ID, "status": {"state": "DISABLED"}},
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(state="DISABLED"),
        )

        client = _client()
        result = client.targets.set_mcp_server_state(_SERVER_ID, "DISABLED")

        assert isinstance(result, McpServerResponse)
        assert result.id == _SERVER_ID
        assert result.state is not None
        assert result.state.value == "DISABLED"


class TestListPredefinedMcpServers:
    def test_list_returns_typed_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )

        client = _client()
        result = client.targets.list_predefined_mcp_servers()

        assert isinstance(result, PredefinedMcpListResponse)
        assert len(result.targets) == 1
        target = result.targets[0]
        assert target.id == _PREDEFINED_ID
        assert target.name == "Context7"
        assert target.category == McpCategory.DEVELOPER_TOOLS_AND_SOURCE_CONTROL
        assert not hasattr(target, "tools")


class TestGetPredefinedMcpServer:
    def test_get_returns_detail_with_tools(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers/{_PREDEFINED_ID}",
            json=_predefined_detail(),
        )

        client = _client()
        result = client.targets.get_predefined_mcp_server(_PREDEFINED_ID)

        assert isinstance(result, PredefinedMcpTargetDetail)
        assert result.id == _PREDEFINED_ID
        assert result.name == "Context7"
        assert len(result.tools) == 1
        assert result.tools[0].name == "search"
        assert result.tools[0].description == "Search the docs"
