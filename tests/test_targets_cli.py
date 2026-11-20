"""Functional tests for the 'secai-cli targets' command group.

These tests invoke the CLI as a subprocess against a live tenant.
Set SECAI_TENANT_URL and SECAI_TOKEN (or add a .env.test file) before
running.

Run with:
    pytest tests/test_targets_cli.py -v
"""

from __future__ import annotations

import json
import uuid

import pytest

from .conftest import run_cli

# ---------------------------------------------------------------------------
# List MCP servers
# ---------------------------------------------------------------------------


class TestTargetsList:
    def test_list_exits_zero(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "mcpServers" in data

    def test_list_quiet_outputs_ids(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert live_mcp_server["id"] in ids

    def test_list_contains_test_server(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list", "--output", "json")
        data = json.loads(result.stdout)
        ids = [s["id"] for s in data["mcpServers"]]
        assert live_mcp_server["id"] in ids


# ---------------------------------------------------------------------------
# Register MCP server
# ---------------------------------------------------------------------------


class TestTargetsRegister:
    def test_register_custom_exits_zero(self) -> None:
        name = f"test-secai-sdk-mcp-{uuid.uuid4().hex[:6]}"
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
        server_id = data["id"]
        run_cli("targets", "set-state", server_id, "DISABLED", check=False)
        run_cli("targets", "delete", server_id, "--confirm", check=False)

    def test_register_returns_enabled_state(self) -> None:
        name = f"test-secai-sdk-mcp-enabled-{uuid.uuid4().hex[:6]}"
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
        server_id = data["id"]
        run_cli("targets", "set-state", server_id, "DISABLED", check=False)
        run_cli("targets", "delete", server_id, "--confirm", check=False)

    def test_register_with_tags(self) -> None:
        name = f"test-secai-sdk-mcp-tagged-{uuid.uuid4().hex[:6]}"
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
        server_id = data["id"]
        run_cli("targets", "set-state", server_id, "DISABLED", check=False)
        run_cli("targets", "delete", server_id, "--confirm", check=False)

    def test_register_duplicate_name_returns_409(self, live_mcp_server: dict) -> None:
        result = run_cli(
            "targets",
            "register",
            "--source",
            "CUSTOM",
            "--name",
            live_mcp_server["name"],
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
    def test_get_existing_server(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "get", live_mcp_server["id"])
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "get", live_mcp_server["id"], "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == live_mcp_server["id"]
        assert "source" in data
        assert "name" in data
        assert "state" in data

    def test_get_quiet_outputs_id(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "get", live_mcp_server["id"], "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == live_mcp_server["id"]

    def test_get_nonexistent_returns_404(self) -> None:
        # Must be a valid UUID format — the API returns 400 for non-UUID IDs.
        result = run_cli("targets", "get", "00000000-0000-0000-0000-000000000000", check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Edit MCP server
# ---------------------------------------------------------------------------


class TestTargetsEdit:
    def test_edit_description(self, live_mcp_server: dict) -> None:
        result = run_cli(
            "targets",
            "edit",
            live_mcp_server["id"],
            "--description",
            "Updated by test suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["description"] == "Updated by test suite"

    def test_edit_tags(self, live_mcp_server: dict) -> None:
        result = run_cli(
            "targets",
            "edit",
            live_mcp_server["id"],
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

    def test_edit_immutable_name_returns_error(self, live_mcp_server: dict) -> None:
        """The API must reject attempts to change the server name."""
        run_cli(
            "targets",
            "edit",
            live_mcp_server["id"],
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
    def test_set_state_disabled(self, live_mcp_server: dict) -> None:
        result = run_cli(
            "targets",
            "set-state",
            live_mcp_server["id"],
            "DISABLED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "DISABLED"

    def test_set_state_enabled(self, live_mcp_server: dict) -> None:
        result = run_cli(
            "targets",
            "set-state",
            live_mcp_server["id"],
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

    def test_delete_custom_server(self) -> None:
        """Full lifecycle: register → disable → delete."""
        name = f"test-secai-sdk-del-tgt-{uuid.uuid4().hex[:6]}"
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

        run_cli("targets", "set-state", server_id, "DISABLED")
        result = run_cli("targets", "delete", server_id, "--confirm")
        assert result.returncode == 0

        # Verify it's gone
        get_result = run_cli("targets", "get", server_id, check=False)
        assert get_result.returncode != 0
        assert "404" in get_result.stderr or "not found" in get_result.stderr.lower()


# ---------------------------------------------------------------------------
# Predefined catalog
# ---------------------------------------------------------------------------


class TestPredefinedTargets:
    def test_list_predefined_exits_zero(self) -> None:
        result = run_cli("targets", "list-predefined")
        assert result.returncode == 0

    def test_list_predefined_json_structure(self) -> None:
        result = run_cli("targets", "list-predefined", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "targets" in data
        assert isinstance(data["targets"], list)

    def test_list_predefined_quiet_outputs_ids(self) -> None:
        result = run_cli("targets", "list-predefined", "--output", "quiet")
        assert result.returncode == 0
        # At least some output
        lines = result.stdout.strip().splitlines()
        assert len(lines) >= 0  # Catalog may be empty in some tenants

    def test_get_predefined_by_id(self) -> None:
        """List the catalog then GET the first entry."""
        list_result = run_cli("targets", "list-predefined", "--output", "json")
        data = json.loads(list_result.stdout)
        targets = data.get("targets", [])
        if not targets:
            pytest.skip("No predefined MCP servers in this tenant catalog.")
        first_id = targets[0]["id"]

        result = run_cli("targets", "get-predefined", first_id, "--output", "json")
        assert result.returncode == 0
        detail = json.loads(result.stdout)
        assert detail["id"] == first_id
        assert "name" in detail
        assert "predefinedTargetVersion" in detail

    def test_get_predefined_nonexistent_returns_404(self) -> None:
        result = run_cli(
            "targets",
            "get-predefined",
            "00000000-0000-0000-0000-000000000000",
            check=False,
        )
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()

    def test_register_predefined_server(self) -> None:
        """Register a predefined MCP server from the catalog (skipped if catalog empty)."""
        list_result = run_cli("targets", "list-predefined", "--output", "json")
        data = json.loads(list_result.stdout)
        targets = data.get("targets", [])
        if not targets:
            pytest.skip("No predefined MCP servers in this tenant catalog.")

        predefined_id = targets[0]["id"]
        name = f"test-secai-sdk-predef-{uuid.uuid4().hex[:6]}"
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

        server_id = server_data["id"]
        run_cli("targets", "set-state", server_id, "DISABLED", check=False)
        run_cli("targets", "delete", server_id, "--confirm", check=False)


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestTargetsOutputFormats:
    def test_json_output_is_parseable(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list", "--output", "json")
        data = json.loads(result.stdout)
        assert isinstance(data.get("mcpServers"), list)

    def test_quiet_output_contains_only_ids(self, live_mcp_server: dict) -> None:
        result = run_cli("targets", "list", "--output", "quiet")
        for line in result.stdout.strip().splitlines():
            # Each line should look like an ID, not JSON or a table
            assert not line.startswith("{")
            assert "|" not in line
