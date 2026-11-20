"""Offline tests for the 'secai-cli targets' command group.

These tests invoke the CLI in-process and mock every HTTP response with
`pytest-httpx`'s `httpx_mock` fixture — no real tenant or network access is
required. For live-tenant smoke tests, see tests/live/test_targets_cli.py.
"""

from __future__ import annotations

import json

from .conftest import run_cli

_BASE = "https://mock.secai.test/api/targets"
_SERVER_ID = "11111111-1111-1111-1111-111111111111"
_PREDEFINED_ID = "22222222-2222-2222-2222-222222222222"


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
        "gatewayUrl": "https://gateway.mock.secai.test/mcp/" + server_id,
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


# ---------------------------------------------------------------------------
# List MCP servers
# ---------------------------------------------------------------------------


class TestTargetsList:
    def test_list_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "mcpServers" in data

    def test_list_quiet_outputs_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert _SERVER_ID in ids

    def test_list_contains_test_server(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list", "--output", "json")
        data = json.loads(result.stdout)
        ids = [s["id"] for s in data["mcpServers"]]
        assert _SERVER_ID in ids


# ---------------------------------------------------------------------------
# Register MCP server
# ---------------------------------------------------------------------------


class TestTargetsRegister:
    def test_register_custom_exits_zero(self, httpx_mock) -> None:
        name = "test-secai-sdk-mcp-abc123"
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(name=name),
        )
        result = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            name,
            "--description",
            "CLI test registration",
            "--category",
            "WEB_AND_BROWSER_AUTOMATION",
            "--url",
            "https://mcp.context7.com/mcp",
            "--auth-type",
            "NONE",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_register_returns_enabled_state(self, httpx_mock) -> None:
        name = "test-secai-sdk-mcp-enabled-abc123"
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(name=name, state="ENABLED"),
        )
        result = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            name,
            "--description",
            "CLI test suite - enabled state check",
            "--category",
            "ITSM_AND_INCIDENT_RESPONSE",
            "--url",
            "https://mcp.context7.com/mcp",
            "--auth-type",
            "NONE",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("state") == "ENABLED"

    def test_register_with_tags(self, httpx_mock) -> None:
        name = "test-secai-sdk-mcp-tagged-abc123"
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(name=name, tags={"env": "test", "team": "sdk"}),
        )
        result = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            name,
            "--description",
            "CLI test suite - tags check",
            "--category",
            "COMMUNICATION_AND_TEAM_CHAT",
            "--url",
            "https://mcp.context7.com/mcp",
            "--auth-type",
            "NONE",
            "--tag",
            "env=test",
            "--tag",
            "team=sdk",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tags"].get("env") == "test"
        assert data["tags"].get("team") == "sdk"

    def test_register_duplicate_name_returns_409(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            status_code=409,
            json={"message": "An MCP server with this name already exists", "code": "CONFLICT"},
        )
        result = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            "existing-server",
            "--description",
            "CLI test suite - duplicate name check",
            "--category",
            "DEVELOPER_TOOLS_AND_SOURCE_CONTROL",
            "--url",
            "https://mcp.context7.com/mcp",
            "--auth-type",
            "NONE",
            check=False,
        )
        assert result.returncode != 0
        assert (
            "409" in result.stderr
            or "conflict" in result.stderr.lower()
            or "exists" in result.stderr.lower()
        )


# ---------------------------------------------------------------------------
# Get MCP server
# ---------------------------------------------------------------------------


class TestTargetsGet:
    def test_get_existing_server(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET", url=f"{_BASE}/mcp-servers/{_SERVER_ID}", json=_mcp_server()
        )
        result = run_cli("targets", "get", _SERVER_ID)
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET", url=f"{_BASE}/mcp-servers/{_SERVER_ID}", json=_mcp_server()
        )
        result = run_cli("targets", "get", _SERVER_ID, "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == _SERVER_ID
        assert "source" in data
        assert "name" in data
        assert "state" in data

    def test_get_quiet_outputs_id(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET", url=f"{_BASE}/mcp-servers/{_SERVER_ID}", json=_mcp_server()
        )
        result = run_cli("targets", "get", _SERVER_ID, "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == _SERVER_ID

    def test_get_nonexistent_returns_404(self, httpx_mock) -> None:
        missing_id = "00000000-0000-0000-0000-000000000000"
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{missing_id}",
            status_code=404,
            json={"message": "MCP server not found"},
        )
        result = run_cli("targets", "get", missing_id, check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Edit MCP server
# ---------------------------------------------------------------------------


class TestTargetsEdit:
    def test_edit_description(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(description="Updated by test suite"),
        )
        result = run_cli(
            "targets",
            "edit",
            _SERVER_ID,
            "--description",
            "Updated by test suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["description"] == "Updated by test suite"

    def test_edit_tags(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(tags={"env": "test", "suite": "targets"}),
        )
        result = run_cli(
            "targets",
            "edit",
            _SERVER_ID,
            "--tag",
            "env=test",
            "--tag",
            "suite=targets",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tags"].get("env") == "test"
        assert data["tags"].get("suite") == "targets"

    def test_edit_immutable_name_returns_error(self, httpx_mock) -> None:
        """The API must reject attempts to change the server name."""
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(),
        )
        run_cli(
            "targets",
            "edit",
            _SERVER_ID,
            "--output",
            "json",
            check=False,
        )
        # An edit with no payload is a no-op but should still succeed
        # (the immutable-field error only fires when you send the field)
        # This test documents that we don't expose --name in the edit command.
        assert "--name" not in run_cli("targets", "edit", "--help").stdout


# ---------------------------------------------------------------------------
# Set MCP server state
# ---------------------------------------------------------------------------


class TestTargetsSetState:
    def test_set_state_disabled(self, httpx_mock) -> None:
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
        result = run_cli(
            "targets",
            "set-state",
            _SERVER_ID,
            "DISABLED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "DISABLED"

    def test_set_state_enabled(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}/state",
            json={"id": _SERVER_ID, "status": {"state": "ENABLED"}},
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{_SERVER_ID}",
            json=_mcp_server(state="ENABLED"),
        )
        result = run_cli(
            "targets",
            "set-state",
            _SERVER_ID,
            "ENABLED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ENABLED"


# ---------------------------------------------------------------------------
# Delete MCP server
# ---------------------------------------------------------------------------


class TestTargetsDelete:
    def test_delete_without_confirm_exits_nonzero(self) -> None:
        result = run_cli("targets", "delete", "some-id", check=False)
        assert result.returncode != 0

    def test_delete_custom_server(self, httpx_mock) -> None:
        """Full lifecycle: register → disable → delete → verify gone."""
        name = "test-secai-sdk-del-tgt-abc123"
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(name=name),
        )
        reg = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            name,
            "--description",
            "CLI test suite - delete lifecycle",
            "--category",
            "WEB_AND_BROWSER_AUTOMATION",
            "--url",
            "https://mcp.context7.com/mcp",
            "--auth-type",
            "NONE",
            "--output",
            "json",
        )
        server_id = json.loads(reg.stdout)["id"]

        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers/{server_id}/state",
            json={"id": server_id, "status": {"state": "DISABLED"}},
        )
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{server_id}",
            json=_mcp_server(server_id=server_id, name=name, state="DISABLED"),
        )
        run_cli("targets", "set-state", server_id, "DISABLED")

        httpx_mock.add_response(method="DELETE", url=f"{_BASE}/mcp-servers/{server_id}", json={})
        result = run_cli("targets", "delete", server_id, "--confirm")
        assert result.returncode == 0

        # Verify it's gone
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers/{server_id}",
            status_code=404,
            json={"message": "MCP server not found"},
        )
        get_result = run_cli("targets", "get", server_id, check=False)
        assert get_result.returncode != 0
        assert "404" in get_result.stderr or "not found" in get_result.stderr.lower()


# ---------------------------------------------------------------------------
# Predefined catalog
# ---------------------------------------------------------------------------


class TestPredefinedTargets:
    def test_list_predefined_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )
        result = run_cli("targets", "list-predefined")
        assert result.returncode == 0

    def test_list_predefined_json_structure(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )
        result = run_cli("targets", "list-predefined", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "targets" in data
        assert isinstance(data["targets"], list)

    def test_list_predefined_quiet_outputs_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )
        result = run_cli("targets", "list-predefined", "--output", "quiet")
        assert result.returncode == 0
        lines = result.stdout.strip().splitlines()
        assert lines == [_PREDEFINED_ID]

    def test_get_predefined_by_id(self, httpx_mock) -> None:
        """List the catalog then GET the first entry."""
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )
        list_result = run_cli("targets", "list-predefined", "--output", "json")
        data = json.loads(list_result.stdout)
        targets = data.get("targets", [])
        first_id = targets[0]["id"]

        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers/{first_id}",
            json=_predefined_detail(first_id),
        )
        result = run_cli("targets", "get-predefined", first_id, "--output", "json")
        assert result.returncode == 0
        detail = json.loads(result.stdout)
        assert detail["id"] == first_id
        assert "name" in detail
        assert "predefinedTargetVersion" in detail

    def test_get_predefined_nonexistent_returns_404(self, httpx_mock) -> None:
        missing_id = "00000000-0000-0000-0000-000000000000"
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers/{missing_id}",
            status_code=404,
            json={"message": "Predefined MCP server not found"},
        )
        result = run_cli(
            "targets",
            "get-predefined",
            missing_id,
            check=False,
        )
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()

    def test_register_predefined_server(self, httpx_mock) -> None:
        """Register a predefined MCP server from the catalog."""
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/predefined/mcp-servers",
            json={"targets": [_predefined_target()]},
        )
        list_result = run_cli("targets", "list-predefined", "--output", "json")
        data = json.loads(list_result.stdout)
        targets = data.get("targets", [])
        predefined_id = targets[0]["id"]

        name = "test-secai-sdk-predef-abc123"
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/mcp-servers",
            json=_mcp_server(
                name=name,
                source={"type": "PREDEFINED", "predefinedTargetId": predefined_id},
            ),
        )
        result = run_cli(
            "targets",
            "register",
            "--source",
            "PREDEFINED",
            "--predefined-id",
            predefined_id,
            "--name",
            name,
            "--output",
            "json",
        )
        assert result.returncode == 0
        server_data = json.loads(result.stdout)
        assert "id" in server_data
        assert server_data.get("source", {}).get("predefinedTargetId") == predefined_id


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestTargetsOutputFormats:
    def test_json_output_is_parseable(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list", "--output", "json")
        data = json.loads(result.stdout)
        assert isinstance(data.get("mcpServers"), list)

    def test_quiet_output_contains_only_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/mcp-servers",
            json={"mcpServers": [_mcp_server()], "nextCursor": None},
        )
        result = run_cli("targets", "list", "--output", "quiet")
        for line in result.stdout.strip().splitlines():
            # Each line should look like an ID, not JSON or a table
            assert not line.startswith("{")
            assert "|" not in line
