"""Offline tests for the 'secai-cli policies' command group.

These tests invoke the CLI in-process and mock every HTTP response with
`pytest-httpx`'s `httpx_mock` fixture — no real tenant or network access is
required. For live-tenant smoke tests, see tests/live/test_policies_cli.py.
"""

from __future__ import annotations

import json

from .conftest import run_cli

_BASE = "https://mock.secai.test/api/policies"

_FAKE_ID = "11111111-1111-1111-1111-111111111111"


def _policy(
    policy_id: str = _FAKE_ID,
    *,
    name: str = "test-policy",
    access_type: str = "AUTONOMOUS",
    state: str = "ENABLED",
    description: str | None = "CLI test registration",
    resources: list[dict] | None = None,
    tags: dict[str, str] | None = None,
) -> dict:
    return {
        "id": policy_id,
        "name": name,
        "description": description,
        "tags": tags or {},
        "owners": [],
        "state": state,
        "accessType": access_type,
        "agent": [{"conditions": [{"op": "any"}]}],
        "user": None,
        "resources": resources
        or [{"conditions": [{"op": "match", "key": "id", "value": "mcp:test-secai-sdk:*"}]}],
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "createdBy": "tester",
        "updatedBy": "tester",
    }


# ---------------------------------------------------------------------------
# List policies
# ---------------------------------------------------------------------------


class TestPoliciesList:
    def test_list_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "policies" in data

    def test_list_quiet_outputs_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert _FAKE_ID in ids

    def test_list_contains_test_policy(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list", "--output", "json")
        data = json.loads(result.stdout)
        ids = [p["id"] for p in data["policies"]]
        assert _FAKE_ID in ids


# ---------------------------------------------------------------------------
# Create policy
# ---------------------------------------------------------------------------


class TestPoliciesCreate:
    def test_create_autonomous_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(method="POST", url=_BASE, status_code=201, json=_policy())
        result = run_cli(
            "policies",
            "create",
            "--name",
            "test-secai-sdk-policy",
            "--access-type",
            "AUTONOMOUS",
            "--description",
            "CLI test registration",
            "--resource-match",
            "mcp:test-secai-sdk:*",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_returns_enabled_state_by_default(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST", url=_BASE, status_code=201, json=_policy(state="ENABLED")
        )
        result = run_cli(
            "policies",
            "create",
            "--name",
            "test-secai-sdk-policy-enabled",
            "--access-type",
            "AUTONOMOUS",
            "--description",
            "CLI test suite - enabled state check",
            "--resource-match",
            "mcp:test-secai-sdk:*",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("state") == "ENABLED"

    def test_create_with_tags(self, httpx_mock) -> None:
        tags = {"env": "test", "team": "sdk"}
        httpx_mock.add_response(
            method="POST", url=_BASE, status_code=201, json=_policy(tags=tags)
        )
        result = run_cli(
            "policies",
            "create",
            "--name",
            "test-secai-sdk-policy-tagged",
            "--access-type",
            "AUTONOMOUS",
            "--description",
            "CLI test suite - tags check",
            "--resource-match",
            "mcp:test-secai-sdk:*",
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

    def test_create_on_behalf_of_requires_user_role(self) -> None:
        """ON_BEHALF_OF without --user-role-id must fail client-side validation.

        No httpx_mock response is registered: the request must never reach
        the (mocked) network, confirming validation happens client-side.
        """
        result = run_cli(
            "policies",
            "create",
            "--name",
            "test-secai-sdk-policy-obo",
            "--access-type",
            "ON_BEHALF_OF",
            "--resource-match",
            "mcp:test-secai-sdk:*",
            check=False,
        )
        assert result.returncode != 0

    def test_create_missing_required_shows_help(self) -> None:
        result = run_cli("policies", "create", check=False)
        assert result.returncode != 0
        assert "Missing required" in result.stderr or "--name" in result.stderr


# ---------------------------------------------------------------------------
# Get policy
# ---------------------------------------------------------------------------


class TestPoliciesGet:
    def test_get_existing_policy(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_FAKE_ID}", json=_policy())
        result = run_cli("policies", "get", _FAKE_ID)
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_FAKE_ID}", json=_policy())
        result = run_cli("policies", "get", _FAKE_ID, "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == _FAKE_ID
        assert "accessType" in data
        assert "name" in data
        assert "state" in data

    def test_get_quiet_outputs_id(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=f"{_BASE}/{_FAKE_ID}", json=_policy())
        result = run_cli("policies", "get", _FAKE_ID, "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == _FAKE_ID

    def test_get_nonexistent_returns_404(self, httpx_mock) -> None:
        missing_id = "00000000-0000-0000-0000-000000000000"
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/{missing_id}",
            status_code=404,
            json={"code": "NOT_FOUND"},
        )
        result = run_cli("policies", "get", missing_id, check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Update policy
# ---------------------------------------------------------------------------


class TestPoliciesUpdate:
    def test_update_description(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/{_FAKE_ID}",
            json=_policy(description="Updated by test suite"),
        )
        result = run_cli(
            "policies",
            "update",
            _FAKE_ID,
            "--description",
            "Updated by test suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["description"] == "Updated by test suite"

    def test_update_tags(self, httpx_mock) -> None:
        tags = {"env": "test", "suite": "policies"}
        httpx_mock.add_response(
            method="PUT", url=f"{_BASE}/{_FAKE_ID}", json=_policy(tags=tags)
        )
        result = run_cli(
            "policies",
            "update",
            _FAKE_ID,
            "--tag",
            "env=test",
            "--tag",
            "suite=policies",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tags"].get("env") == "test"
        assert data["tags"].get("suite") == "policies"

    def test_update_resource_match(self, httpx_mock) -> None:
        resources = [
            {
                "conditions": [
                    {"op": "match", "key": "id", "value": "mcp:test-secai-sdk-updated:*"}
                ]
            }
        ]
        httpx_mock.add_response(
            method="PUT", url=f"{_BASE}/{_FAKE_ID}", json=_policy(resources=resources)
        )
        result = run_cli(
            "policies",
            "update",
            _FAKE_ID,
            "--resource-match",
            "mcp:test-secai-sdk-updated:*",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["resources"]


# ---------------------------------------------------------------------------
# Set policy state
# ---------------------------------------------------------------------------


class TestPoliciesSetState:
    def test_set_state_disabled(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{_FAKE_ID}/state",
            json={"id": _FAKE_ID, "state": "DISABLED"},
        )
        result = run_cli(
            "policies",
            "set-state",
            _FAKE_ID,
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
            url=f"{_BASE}/{_FAKE_ID}/state",
            json={"id": _FAKE_ID, "state": "ENABLED"},
        )
        result = run_cli(
            "policies",
            "set-state",
            _FAKE_ID,
            "ENABLED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "ENABLED"


# ---------------------------------------------------------------------------
# Delete policy
# ---------------------------------------------------------------------------


class TestPoliciesDelete:
    def test_delete_without_confirm_exits_nonzero(self) -> None:
        """No HTTP mock registered: the CLI must refuse before any request is made."""
        result = run_cli("policies", "delete", "some-id", check=False)
        assert result.returncode != 0

    def test_delete_policy(self, httpx_mock) -> None:
        httpx_mock.add_response(method="DELETE", url=f"{_BASE}/{_FAKE_ID}", status_code=204)
        result = run_cli("policies", "delete", _FAKE_ID, "--confirm")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestPoliciesOutputFormats:
    def test_json_output_is_parseable(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list", "--output", "json")
        data = json.loads(result.stdout)
        assert isinstance(data.get("policies"), list)

    def test_quiet_output_contains_only_ids(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_BASE, json={"policies": [_policy()]})
        result = run_cli("policies", "list", "--output", "quiet")
        for line in result.stdout.strip().splitlines():
            # Each line should look like an ID, not JSON or a table
            assert not line.startswith("{")
            assert "|" not in line
