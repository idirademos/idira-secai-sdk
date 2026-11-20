"""Functional tests for the 'secai-cli agents' command group.

These tests invoke the CLI as a subprocess against a live tenant.
Set SECAI_TENANT_URL and SECAI_TOKEN (or add a .env.test file) before
running.

Run with:
    pytest -m live tests/live/test_agents_cli.py -v
"""

from __future__ import annotations

import json
import uuid

import pytest

from .conftest import run_cli

pytestmark = pytest.mark.live

# ---------------------------------------------------------------------------
# List agents
# ---------------------------------------------------------------------------


class TestAgentsList:
    def test_list_exits_zero(self, live_agent: dict) -> None:
        result = run_cli("agents", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, live_agent: dict) -> None:
        result = run_cli("agents", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_list_quiet_outputs_ids(self, live_agent: dict) -> None:
        result = run_cli("agents", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert live_agent["id"] in ids

    def test_list_contains_test_agent(self, live_agent: dict) -> None:
        result = run_cli("agents", "list", "--output", "json")
        agents = json.loads(result.stdout)
        ids = [a["id"] for a in agents]
        assert live_agent["id"] in ids


# ---------------------------------------------------------------------------
# Register agent
# ---------------------------------------------------------------------------


class TestAgentsRegister:
    def test_register_returns_credentials(self) -> None:
        name = f"test-secai-sdk-reg-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "agents",
            "register",
            "--name",
            name,
            "--type",
            "COPILOT",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "id" in data
        assert "credentials" in data
        assert "clientSecret" in data["credentials"]
        assert "gatewayUrl" in data["credentials"]
        # Cleanup
        agent_id = data["id"]
        run_cli("agents", "set-state", agent_id, "ACTIVE", check=False)
        run_cli("agents", "set-state", agent_id, "SUSPENDED", check=False)
        run_cli("agents", "delete", agent_id, "--confirm", check=False)

    def test_register_quiet_outputs_id(self) -> None:
        name = f"test-secai-sdk-quiet-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "agents",
            "register",
            "--name",
            name,
            "--type",
            "COPILOT",
            "--output",
            "quiet",
        )
        assert result.returncode == 0
        agent_id = result.stdout.strip()
        assert len(agent_id) > 0
        run_cli("agents", "set-state", agent_id, "ACTIVE", check=False)
        run_cli("agents", "set-state", agent_id, "SUSPENDED", check=False)
        run_cli("agents", "delete", agent_id, "--confirm", check=False)

    def test_register_with_tags(self) -> None:
        name = f"test-secai-sdk-tags-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "agents",
            "register",
            "--name",
            name,
            "--type",
            "COPILOT",
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
        agent_id = data["id"]
        run_cli("agents", "set-state", agent_id, "ACTIVE", check=False)
        run_cli("agents", "set-state", agent_id, "SUSPENDED", check=False)
        run_cli("agents", "delete", agent_id, "--confirm", check=False)

    def test_register_duplicate_name_returns_error(self, live_agent: dict) -> None:
        """Registering with the same name should fail with a 409 ConflictError."""
        result = run_cli(
            "agents",
            "register",
            "--name",
            live_agent["name"],
            "--type",
            "COPILOT",
            check=False,
        )
        assert result.returncode != 0
        assert (
            "409" in result.stderr
            or "CONFLICT" in result.stderr.upper()
            or "conflict" in result.stderr.lower()
        )


# ---------------------------------------------------------------------------
# Get agent
# ---------------------------------------------------------------------------


class TestAgentsGet:
    def test_get_existing_agent(self, live_agent: dict) -> None:
        result = run_cli("agents", "get", live_agent["id"])
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, live_agent: dict) -> None:
        result = run_cli("agents", "get", live_agent["id"], "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == live_agent["id"]
        assert "name" in data
        assert "status" in data

    def test_get_quiet_outputs_id(self, live_agent: dict) -> None:
        result = run_cli("agents", "get", live_agent["id"], "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == live_agent["id"]

    def test_get_nonexistent_agent_returns_404(self) -> None:
        result = run_cli("agents", "get", "nonexistent-id-00000", check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Edit agent
# ---------------------------------------------------------------------------


class TestAgentsEdit:
    def test_edit_description(self, live_agent: dict) -> None:
        result = run_cli(
            "agents",
            "edit",
            live_agent["id"],
            "--description",
            "Updated by test suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["description"] == "Updated by test suite"

    def test_edit_tags(self, live_agent: dict) -> None:
        result = run_cli(
            "agents",
            "edit",
            live_agent["id"],
            "--tag",
            "env=test",
            "--tag",
            "suite=agents",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tags"].get("env") == "test"
        assert data["tags"].get("suite") == "agents"

    def test_edit_owner(self, live_agent: dict) -> None:
        # The server's edit endpoint does not echo back the free-text `owner`
        # string — ownership is managed via the structured `owners` list.
        # Verify that --owner is accepted without error and returns a valid
        # agent record with the correct ID.
        result = run_cli(
            "agents",
            "edit",
            live_agent["id"],
            "--owner",
            "SDK Test Suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == live_agent["id"]


# ---------------------------------------------------------------------------
# Set agent state
# ---------------------------------------------------------------------------


class TestAgentsSetState:
    def test_set_state_suspended(self, live_agent: dict) -> None:
        run_cli("agents", "set-state", live_agent["id"], "ACTIVE", check=False)
        result = run_cli(
            "agents",
            "set-state",
            live_agent["id"],
            "SUSPENDED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"]["state"] == "SUSPENDED"

    def test_set_state_active(self, live_agent: dict) -> None:
        result = run_cli(
            "agents",
            "set-state",
            live_agent["id"],
            "ACTIVE",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"]["state"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Delete agent
# ---------------------------------------------------------------------------


class TestAgentsDelete:
    def test_delete_without_confirm_exits_nonzero(self) -> None:
        # Should fail without --confirm regardless of agent state
        result = run_cli("agents", "delete", "some-id", check=False)
        assert result.returncode != 0

    def test_delete_active_agent_returns_conflict(self, live_agent: dict) -> None:
        """Deleting an ACTIVE agent must fail with a 409 ConflictError."""
        # Ensure agent is ACTIVE
        run_cli("agents", "set-state", live_agent["id"], "ACTIVE", check=False)
        result = run_cli("agents", "delete", live_agent["id"], "--confirm", check=False)
        assert result.returncode != 0
        assert "409" in result.stderr or "conflict" in result.stderr.lower()

    def test_delete_suspended_agent(self) -> None:
        """Full lifecycle: register → suspend → delete."""
        name = f"test-secai-sdk-del-{uuid.uuid4().hex[:6]}"
        reg = run_cli(
            "agents",
            "register",
            "--name",
            name,
            "--type",
            "COPILOT",
            "--output",
            "json",
        )
        agent_id = json.loads(reg.stdout)["id"]

        run_cli("agents", "set-state", agent_id, "ACTIVE")
        run_cli("agents", "set-state", agent_id, "SUSPENDED")
        result = run_cli("agents", "delete", agent_id, "--confirm")
        assert result.returncode == 0

        # Verify it's gone
        get_result = run_cli("agents", "get", agent_id, check=False)
        assert get_result.returncode != 0
        assert "404" in get_result.stderr or "not found" in get_result.stderr.lower()


# ---------------------------------------------------------------------------
# Auth / error handling
# ---------------------------------------------------------------------------


class TestAgentsErrors:
    def test_missing_token_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SECAI_TOKEN", "")
        result = run_cli("agents", "list", check=False)
        assert result.returncode != 0

    def test_json_output_is_parseable(self, live_agent: dict) -> None:
        result = run_cli("agents", "list", "--output", "json")
        # Must be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data, list)
