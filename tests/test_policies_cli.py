"""Functional tests for the 'secai-cli policies' command group.

These tests invoke the CLI as a subprocess against a live tenant.
Set SECAI_TENANT_URL and SECAI_TOKEN (or add a .env.test file) before
running.

Run with:
    pytest tests/test_policies_cli.py -v
"""

from __future__ import annotations

import json
import uuid

from .conftest import run_cli

# ---------------------------------------------------------------------------
# List policies
# ---------------------------------------------------------------------------


class TestPoliciesList:
    def test_list_exits_zero(self, live_policy: dict) -> None:
        result = run_cli("policies", "list")
        assert result.returncode == 0

    def test_list_json_is_valid(self, live_policy: dict) -> None:
        result = run_cli("policies", "list", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "policies" in data

    def test_list_quiet_outputs_ids(self, live_policy: dict) -> None:
        result = run_cli("policies", "list", "--output", "quiet")
        assert result.returncode == 0
        ids = result.stdout.strip().splitlines()
        assert live_policy["id"] in ids

    def test_list_contains_test_policy(self, live_policy: dict) -> None:
        result = run_cli("policies", "list", "--output", "json")
        data = json.loads(result.stdout)
        ids = [p["id"] for p in data["policies"]]
        assert live_policy["id"] in ids


# ---------------------------------------------------------------------------
# Create policy
# ---------------------------------------------------------------------------


class TestPoliciesCreate:
    def test_create_autonomous_exits_zero(self) -> None:
        name = f"test-secai-sdk-policy-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "policies",
            "create",
            "--name",
            name,
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
        policy_id = data["id"]
        run_cli("policies", "set-state", policy_id, "DISABLED", check=False)
        run_cli("policies", "delete", policy_id, "--confirm", check=False)

    def test_create_returns_enabled_state_by_default(self) -> None:
        name = f"test-secai-sdk-policy-enabled-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "policies",
            "create",
            "--name",
            name,
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
        policy_id = data["id"]
        run_cli("policies", "set-state", policy_id, "DISABLED", check=False)
        run_cli("policies", "delete", policy_id, "--confirm", check=False)

    def test_create_with_tags(self) -> None:
        name = f"test-secai-sdk-policy-tagged-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "policies",
            "create",
            "--name",
            name,
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
        policy_id = data["id"]
        run_cli("policies", "set-state", policy_id, "DISABLED", check=False)
        run_cli("policies", "delete", policy_id, "--confirm", check=False)

    def test_create_on_behalf_of_requires_user_role(self) -> None:
        """ON_BEHALF_OF without --user-role-id must fail client-side validation."""
        name = f"test-secai-sdk-policy-obo-{uuid.uuid4().hex[:6]}"
        result = run_cli(
            "policies",
            "create",
            "--name",
            name,
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
    def test_get_existing_policy(self, live_policy: dict) -> None:
        result = run_cli("policies", "get", live_policy["id"])
        assert result.returncode == 0

    def test_get_json_has_expected_fields(self, live_policy: dict) -> None:
        result = run_cli("policies", "get", live_policy["id"], "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == live_policy["id"]
        assert "accessType" in data
        assert "name" in data
        assert "state" in data

    def test_get_quiet_outputs_id(self, live_policy: dict) -> None:
        result = run_cli("policies", "get", live_policy["id"], "--output", "quiet")
        assert result.returncode == 0
        assert result.stdout.strip() == live_policy["id"]

    def test_get_nonexistent_returns_404(self) -> None:
        result = run_cli("policies", "get", "00000000-0000-0000-0000-000000000000", check=False)
        assert result.returncode != 0
        assert "404" in result.stderr or "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Update policy
# ---------------------------------------------------------------------------


class TestPoliciesUpdate:
    def test_update_description(self, live_policy: dict) -> None:
        result = run_cli(
            "policies",
            "update",
            live_policy["id"],
            "--description",
            "Updated by test suite",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["description"] == "Updated by test suite"

    def test_update_tags(self, live_policy: dict) -> None:
        result = run_cli(
            "policies",
            "update",
            live_policy["id"],
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

    def test_update_resource_match(self, live_policy: dict) -> None:
        result = run_cli(
            "policies",
            "update",
            live_policy["id"],
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
    def test_set_state_disabled(self, live_policy: dict) -> None:
        result = run_cli(
            "policies",
            "set-state",
            live_policy["id"],
            "DISABLED",
            "--output",
            "json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["state"] == "DISABLED"

    def test_set_state_enabled(self, live_policy: dict) -> None:
        result = run_cli(
            "policies",
            "set-state",
            live_policy["id"],
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
        result = run_cli("policies", "delete", "some-id", check=False)
        assert result.returncode != 0

    def test_delete_policy(self) -> None:
        """Full lifecycle: create → disable → delete."""
        name = f"test-secai-sdk-del-policy-{uuid.uuid4().hex[:6]}"
        reg = run_cli(
            "policies",
            "create",
            "--name",
            name,
            "--access-type",
            "AUTONOMOUS",
            "--description",
            "CLI test suite - delete lifecycle",
            "--resource-match",
            "mcp:test-secai-sdk:*",
            "--output",
            "json",
        )
        policy_id = json.loads(reg.stdout)["id"]

        run_cli("policies", "set-state", policy_id, "DISABLED")
        result = run_cli("policies", "delete", policy_id, "--confirm")
        assert result.returncode == 0

        # Verify it's gone
        get_result = run_cli("policies", "get", policy_id, check=False)
        assert get_result.returncode != 0
        assert "404" in get_result.stderr or "not found" in get_result.stderr.lower()


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestPoliciesOutputFormats:
    def test_json_output_is_parseable(self, live_policy: dict) -> None:
        result = run_cli("policies", "list", "--output", "json")
        data = json.loads(result.stdout)
        assert isinstance(data.get("policies"), list)

    def test_quiet_output_contains_only_ids(self, live_policy: dict) -> None:
        result = run_cli("policies", "list", "--output", "quiet")
        for line in result.stdout.strip().splitlines():
            # Each line should look like an ID, not JSON or a table
            assert not line.startswith("{")
            assert "|" not in line
