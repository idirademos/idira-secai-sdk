"""Offline tests for the 'secai-cli agents' command group.

These tests invoke the CLI in-process and mock every HTTP response with
`pytest-httpx`'s `httpx_mock` fixture — no real tenant or network access is
required. For live-tenant smoke tests, see tests/live/test_agents_cli.py.
"""

from __future__ import annotations

import json

from .conftest import run_cli

_BASE = "https://mock.secai.test/api/agents"

_AGENT_ID = "11111111-1111-1111-1111-111111111111"
_AGENT_NAME = "test-secai-sdk-agent"


def _agent(
    *,
    agent_id: str = _AGENT_ID,
    name: str = _AGENT_NAME,
    agent_type: str = "COPILOT",
    description: str | None = None,
    owner: str | None = None,
    tags: dict[str, str] | None = None,
    state: str = "ACTIVE",
) -> dict:
    """Build a realistic Agent JSON payload (camelCase, as the API returns it)."""
    return {
        "id": agent_id,
        "name": name,
        "type": agent_type,
        "description": description,
        "owner": owner,
        "owners": [],
        "redirectCallbackUrls": [],
        "tags": tags or {},
        "clientId": f"client-{agent_id}",
        "status": {"state": state, "message": None},
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-02T00:00:00Z",
        "createdBy": "tester",
        "updatedBy": "tester",
        "agentSubtype": None,
        "originId": None,
        "lastUsed": None,
        "authnDescriptors": [],
    }


def _agent_with_credentials(**kwargs) -> dict:
    agent = _agent(**kwargs)
    agent["credentials"] = {
        "clientId": agent["clientId"],
        "clientSecret": "s3cr3t-client-secret",
        "gatewayUrl": "https://gateway.mock.secai.test",
    }
    return agent


def _list_response(agents: list[dict]) -> dict:
    return {"agents": agents, "pageInfo": None, "totalCount": len(agents)}


def _error_body(message: str, code: str) -> dict:
    return {"message": message, "code": code}


# ---------------------------------------------------------------------------
# List agents
# ---------------------------------------------------------------------------


class TestAgentsList:
    def test_list_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json=_list_response([_agent()]))
        result = run_cli("agents", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json=_list_response([_agent()]))
        result = run_cli("agents", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data["agents"], list)

    def test_list_quiet_outputs_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json=_list_response([_agent()]))
        result = run_cli("agents", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert _AGENT_ID in ids

    def test_list_contains_test_agent(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json=_list_response([_agent()]))
        result = run_cli("agents", "list", "--output", "json")
        data = json.loads(result.stdout)
        ids = [a["id"] for a in data["agents"]]
        assert _AGENT_ID in ids


# ---------------------------------------------------------------------------
# Register agent
# ---------------------------------------------------------------------------


class TestAgentsRegister:
    def test_register_returns_credentials(self, httpx_mock) -> None:
        httpx_mock.add_response(method="POST", url=_BASE, json=_agent_with_credentials())
        result = run_cli(
            "agents",
            "register",
            "--name",
            _AGENT_NAME,
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

    def test_register_quiet_outputs_id(self, httpx_mock) -> None:
        httpx_mock.add_response(method="POST", url=_BASE, json=_agent_with_credentials())
        result = run_cli(
            "agents",
            "register",
            "--name",
            _AGENT_NAME,
            "--type",
            "COPILOT",
            "--output",
            "quiet",
        )
        assert result.returncode == 0
        agent_id = result.stdout.strip()
        assert len(agent_id) > 0

    def test_register_with_tags(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=_BASE,
            json=_agent_with_credentials(tags={"env": "test", "team": "sdk"}),
        )
        result = run_cli(
            "agents",
            "register",
            "--name",
            _AGENT_NAME,
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

    def test_register_duplicate_name_returns_error(self, httpx_mock) -> None:
        """Registering with the same name should fail with a 409 ConflictError."""
        httpx_mock.add_response(
            method="POST",
            url=_BASE,
            status_code=409,
            json=_error_body("Agent name already in use", "CONFLICT"),
        )
        result = run_cli(
            "agents",
            "register",
            "--name",
            _AGENT_NAME,
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
    def test_get_existing_agent(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_AGENT_ID}", json=_agent())
        result = run_cli("agents", "get", _AGENT_ID)
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_AGENT_ID}", json=_agent())
        result = run_cli("agents", "get", _AGENT_ID, "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == _AGENT_ID
        assert "name" in data
        assert "status" in data

    def test_get_table_shows_authn_descriptors(self, httpx_mock) -> None:
        body = _agent()
        body["authnDescriptors"] = [
            {
                "id": "desc-1",
                "type": "SPIFFE",
                "data": {"spiffeId": "spiffe://example.org/agent"},
                "clientSecret": "do-not-print",
            }
        ]
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_AGENT_ID}", json=body)
        result = run_cli("agents", "get", _AGENT_ID, "--output", "table")
        assert result.returncode == 0
        assert "Authn descriptors (1)" in result.stdout
        assert "desc-1" in result.stdout
        assert "SPIFFE" in result.stdout
        assert "do-not-print" not in result.stdout

    def test_get_quiet_outputs_id(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_AGENT_ID}", json=_agent())
        result = run_cli("agents", "get", _AGENT_ID, "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == _AGENT_ID

    def test_get_nonexistent_agent_returns_404(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/nonexistent-id-00000",
            status_code=404,
            json=_error_body("Agent not found", "NOT_FOUND"),
        )
        result = run_cli("agents", "get", "nonexistent-id-00000", check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Edit agent
# ---------------------------------------------------------------------------


class TestAgentsEdit:
    def test_edit_description(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/{_AGENT_ID}",
            json=_agent(description="Updated by test suite"),
        )
        result = run_cli(
            "agents",
            "edit",
            _AGENT_ID,
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
            url=f"{_BASE}/{_AGENT_ID}",
            json=_agent(tags={"env": "test", "suite": "agents"}),
        )
        result = run_cli(
            "agents",
            "edit",
            _AGENT_ID,
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

    def test_edit_owner(self, httpx_mock) -> None:
        # The server's edit endpoint does not echo back the free-text `owner`
        # string — ownership is managed via the structured `owners` list.
        # Verify that --owner is accepted without error and returns a valid
        # agent record with the correct ID.
        httpx_mock.add_response(method="PUT", url=f"{_BASE}/{_AGENT_ID}", json=_agent())
        result = run_cli(
            "agents",
            "edit",
            _AGENT_ID,
            "--owner",
            "SDK Test Suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == _AGENT_ID


# ---------------------------------------------------------------------------
# Set agent state
# ---------------------------------------------------------------------------


class TestAgentsSetState:
    def test_set_state_suspended(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{_AGENT_ID}/state",
            json={"id": _AGENT_ID, "status": {"state": "SUSPENDED", "message": None}},
        )
        result = run_cli(
            "agents",
            "set-state",
            _AGENT_ID,
            "SUSPENDED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"]["state"] == "SUSPENDED"

    def test_set_state_active(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{_AGENT_ID}/state",
            json={"id": _AGENT_ID, "status": {"state": "ACTIVE", "message": None}},
        )
        result = run_cli(
            "agents",
            "set-state",
            _AGENT_ID,
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
    def test_delete_without_confirm_exits_nonzero(self, httpx_mock) -> None:
        # Should fail without --confirm before any HTTP request is made.
        result = run_cli("agents", "delete", "some-id", check=False)
        assert result.returncode != 0

    def test_delete_active_agent_returns_conflict(self, httpx_mock) -> None:
        """Deleting an ACTIVE agent must fail with a 409 ConflictError."""
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_BASE}/{_AGENT_ID}",
            status_code=409,
            json=_error_body("Agent is ACTIVE and cannot be deleted", "CONFLICT"),
        )
        result = run_cli("agents", "delete", _AGENT_ID, "--confirm", check=False)
        assert result.returncode != 0
        assert "409" in result.stderr or "conflict" in result.stderr.lower()

    def test_delete_suspended_agent(self, httpx_mock) -> None:
        """Full lifecycle: register -> suspend -> delete -> verify gone."""
        agent_id = "22222222-2222-2222-2222-222222222222"
        httpx_mock.add_response(
            method="POST", url=_BASE, json=_agent_with_credentials(agent_id=agent_id)
        )
        reg = run_cli(
            "agents",
            "register",
            "--name",
            "test-secai-sdk-del",
            "--type",
            "COPILOT",
            "--output",
            "json",
        )
        assert json.loads(reg.stdout)["id"] == agent_id

        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{agent_id}/state",
            json={"id": agent_id, "status": {"state": "ACTIVE", "message": None}},
        )
        run_cli("agents", "set-state", agent_id, "ACTIVE")

        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{agent_id}/state",
            json={"id": agent_id, "status": {"state": "SUSPENDED", "message": None}},
        )
        run_cli("agents", "set-state", agent_id, "SUSPENDED")

        httpx_mock.add_response(method="DELETE", url=f"{_BASE}/{agent_id}", status_code=204)
        result = run_cli("agents", "delete", agent_id, "--confirm")
        assert result.returncode == 0

        # Verify it's gone
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/{agent_id}",
            status_code=404,
            json=_error_body("Agent not found", "NOT_FOUND"),
        )
        get_result = run_cli("agents", "get", agent_id, check=False)
        assert get_result.returncode != 0
        assert "404" in get_result.stderr or "not found" in get_result.stderr.lower()


# ---------------------------------------------------------------------------
# Auth / error handling
# ---------------------------------------------------------------------------


class TestAgentsErrors:
    def test_missing_token_returns_401(self, httpx_mock) -> None:
        # With no token at all, SecAIClient.__init__ raises ValueError before
        # any HTTP request is made (no credentials to authenticate with), so
        # no response needs to be mocked here.
        result = run_cli("agents", "list", check=False, env={"SECAI_TOKEN": ""})
        assert result.returncode != 0

    def test_json_output_is_parseable(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json=_list_response([_agent()]))
        result = run_cli("agents", "list", "--output", "json")
        # Must be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data["agents"], list)
