"""Shared pytest fixtures for the SecAI SDK CLI test suite.

Environment variables required (set in .env.test or exported):
  SECAI_TENANT_URL  — e.g. https://mytenant.cyberark.cloud
  SECAI_TOKEN       — valid Bearer JWT

The fixtures in this module create real resources in the tenant at
session scope and tear them down afterwards.  All resource names are
prefixed with ``test-secai-sdk-`` for easy identification.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PREFIX = "test-secai-sdk"


def _unique(suffix: str) -> str:
    short = uuid.uuid4().hex[:6]
    return f"{PREFIX}-{suffix}-{short}"


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Invoke secai-cli as a subprocess and return the result."""
    env = {**os.environ}
    result = subprocess.run(
        ["secai-cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"CLI exited {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


# ---------------------------------------------------------------------------
# Session-scoped agent fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_agent() -> Generator[dict[str, str], None, None]:
    """Register a test agent; yield its id; delete it after the session."""
    name = _unique("agent")
    result = run_cli(
        "agents", "register",
        "--name", name,
        "--type", "COPILOT",
        "--description", "Created by secai-sdk test suite",
        "--owner", "SDK Tests",
        "--tag", "env=test",
        "--output", "json",
    )
    import json
    data = json.loads(result.stdout)
    agent_id: str = data["id"]
    yield {
        "id": agent_id,
        "name": name,
        "client_id": data.get("credentials", {}).get("clientId", ""),
    }
    # Teardown — activate → suspend → delete
    try:
        run_cli("agents", "set-state", agent_id, "ACTIVE", check=False)
        run_cli("agents", "set-state", agent_id, "SUSPENDED", check=False)
        run_cli("agents", "delete", agent_id, "--confirm", check=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session-scoped MCP server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_mcp_server() -> Generator[dict[str, str], None, None]:
    """Register a test custom MCP server; yield its id; disable and delete after session."""
    name = _unique("mcp")
    result = run_cli(
        "targets", "register",
        "--source", "CUSTOM",
        "--name", name,
        "--description", "Created by secai-sdk test suite",
        "--category", "DEVELOPER_TOOLS_AND_SOURCE_CONTROL",
        "--url", "https://mcp.context7.com/mcp",
        "--auth-type", "NONE",
        "--tag", "env=test",
        "--output", "json",
    )
    import json
    data = json.loads(result.stdout)
    server_id: str = data["id"]
    yield {"id": server_id, "name": name}
    # Teardown
    try:
        run_cli("targets", "set-state", server_id, "DISABLED", check=False)
        run_cli("targets", "delete", server_id, "--confirm", check=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session-scoped policy fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_policy() -> Generator[dict[str, str], None, None]:
    """Create a test access policy; yield its id; disable and delete after session."""
    name = _unique("policy")
    result = run_cli(
        "policies", "create",
        "--name", name,
        "--access-type", "AUTONOMOUS",
        "--description", "Created by secai-sdk test suite",
        "--resource-match", "mcp:test-secai-sdk:*",
        "--tag", "env=test",
        "--output", "json",
    )
    import json
    data = json.loads(result.stdout)
    policy_id: str = data["id"]
    yield {"id": policy_id, "name": name}
    # Teardown
    try:
        run_cli("policies", "set-state", policy_id, "DISABLED", check=False)
        run_cli("policies", "delete", policy_id, "--confirm", check=False)
    except Exception:
        pass
