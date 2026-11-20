#!/usr/bin/env python3
"""SecAI SDK Quickstart

Demonstrates the full lifecycle of an agent, an MCP server target, and an
access policy:
  1. List existing agents
  2. Register a new agent (get credentials)
  3. Edit agent metadata
  4. Register a custom MCP server target
  5. Browse the predefined MCP catalog
  6. Create an access policy granting the agent access to the MCP server
  7. Download the tenant's insights and activity map report
  8. Clean up — disable/delete the policy, agent, and MCP server

Prerequisites:
  pip install secai

Environment variables (or set in a .env file):
  SECAI_TENANT_URL  — e.g. https://mytenant.cyberark.cloud
  SECAI_TOKEN       — valid Bearer JWT
"""

import os
import sys

# Load a .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from secai import (
    EditAgentRequest,
    EditMcpServerRequest,
    McpAuthMethod,
    McpAuthType,
    McpCategory,
    McpUpstream,
    PolicyInput,
    PolicyState,
    RegisterAgentRequest,
    RegisterCustomMcpServerRequest,
    SecAIClient,
)
from secai.models import Condition, ConditionGroup


def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Create the client
    # -----------------------------------------------------------------------
    tenant_url = os.environ.get("SECAI_TENANT_URL")
    token = os.environ.get("SECAI_TOKEN")

    if not tenant_url or not token:
        print(
            "ERROR: Set SECAI_TENANT_URL and SECAI_TOKEN before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = SecAIClient(tenant_url=tenant_url, token=token)

    # -----------------------------------------------------------------------
    # 2. List existing agents
    # -----------------------------------------------------------------------
    print("── Existing agents ──────────────────────────────────────────────")
    agents_page = client.agents.list(page_size=50)
    if agents_page.agents:
        for a in agents_page.agents:
            state = a.status.state.value if a.status else "unknown"
            print(f"  {a.id}  {a.name:<30}  {state}")
    else:
        print("  (none)")

    # -----------------------------------------------------------------------
    # 3. Register a new agent
    # -----------------------------------------------------------------------
    print("\n── Registering agent ────────────────────────────────────────────")
    new_agent = client.agents.register(
        RegisterAgentRequest(
            name="SDK Quickstart Agent",
            type="COPILOT",
            description="Created by the SecAI SDK quickstart example.",
            owner="SDK Team",
            # redirectCallbackUrls are auto-filled by the server for predefined
            # types (COPILOT, CLAUDE).  Only CUSTOM agents require manual URLs.
            tags={"environment": "demo", "team": "sdk"},
        )
    )
    print(f"  Registered : {new_agent.id}")
    print(f"  Name       : {new_agent.name}")
    print(f"  State      : {new_agent.status.state.value if new_agent.status else '—'}")
    if new_agent.credentials:
        print(f"  Client ID  : {new_agent.credentials.client_id or '—'}")
        print(
            f"  Secret     : {new_agent.credentials.client_secret or '—'}  "
            "← store securely; shown once"
        )
        print(f"  Gateway    : {new_agent.credentials.gateway_url or '—'}")

    # -----------------------------------------------------------------------
    # 4. Edit agent metadata
    # -----------------------------------------------------------------------
    print("\n── Editing agent ────────────────────────────────────────────────")
    updated_agent = client.agents.edit(
        new_agent.id,
        EditAgentRequest(
            description="Updated description from the quickstart.",
            tags={"environment": "demo", "team": "sdk", "quickstart": "true"},
        ),
    )
    # A 204 (None) means the request matched the stored agent exactly —
    # nothing was written or audited.
    if updated_agent is None:
        print("  (no changes — request matched the stored agent)")
    else:
        print(f"  Description: {updated_agent.description}")
        print(f"  Tags       : {updated_agent.tags}")

    # -----------------------------------------------------------------------
    # 5. Register a custom MCP server target
    # -----------------------------------------------------------------------
    print("\n── Registering MCP server ───────────────────────────────────────")
    mcp_server = client.targets.register_mcp_server(
        RegisterCustomMcpServerRequest(
            name="SDK Quickstart MCP Server",
            description="Demo MCP server created by the quickstart example.",
            category=McpCategory.DEVELOPER_TOOLS_AND_SOURCE_CONTROL,
            upstream=McpUpstream(url="https://mcp.context7.com/mcp"),
            authMethod=McpAuthMethod(type=McpAuthType.NONE),
            tags={"environment": "demo"},
        )
    )
    print(f"  Registered : {mcp_server.id}")
    print(f"  Name       : {mcp_server.name}")
    print(f"  State      : {mcp_server.state.value if mcp_server.state else '—'}")
    print(f"  Gateway    : {mcp_server.gateway_url or '—'}")

    # -----------------------------------------------------------------------
    # 6. Update the MCP server description
    # -----------------------------------------------------------------------
    print("\n── Editing MCP server ───────────────────────────────────────────")
    updated_mcp = client.targets.edit_mcp_server(
        mcp_server.id,
        EditMcpServerRequest(
            description="Updated description from the quickstart.",
            tags={"environment": "demo", "quickstart": "true"},
        ),
    )
    print(f"  Description: {updated_mcp.description}")

    # -----------------------------------------------------------------------
    # 7. Browse the predefined MCP catalog
    # -----------------------------------------------------------------------
    print("\n── Predefined MCP catalog ───────────────────────────────────────")
    catalog = client.targets.list_predefined_mcp_servers()
    if catalog.targets:
        for tmpl in catalog.targets:
            cat = tmpl.category.value if tmpl.category else "—"
            print(f"  {tmpl.id}  {tmpl.name:<35}  {cat}")

        # Fetch details for the first template, including its tools
        first = catalog.targets[0]
        detail = client.targets.get_predefined_mcp_server(first.id)
        print("\n  First template detail:")
        print(f"    Name    : {detail.name}")
        print(f"    Version : {detail.predefined_target_version}")
        auth = detail.auth_method.type.value if detail.auth_method else "—"
        print(f"    Auth    : {auth}")
        for tool in detail.tools:
            print(f"    Tool    : {tool.name} — {tool.description}")
    else:
        print("  (no predefined templates in this tenant)")

    # -----------------------------------------------------------------------
    # 8. Create an access policy for the new agent
    # -----------------------------------------------------------------------
    print("\n── Creating access policy ───────────────────────────────────────")
    policy = client.policies.create(
        PolicyInput(
            name="Quickstart agent autonomous access",
            description="Allows the quickstart agent to call the quickstart MCP server.",
            accessType="AUTONOMOUS",
            state=PolicyState.ENABLED,
            agent=[ConditionGroup(conditions=[Condition(op="in", key="id", value=[new_agent.id])])],
            resources=[
                ConditionGroup(
                    conditions=[Condition(op="match", key="id", value=f"mcp:{mcp_server.id}:*")]
                )
            ],
            tags={"environment": "demo"},
        )
    )
    print(f"  Created   : {policy.id}")
    print(f"  Name      : {policy.name}")
    print(f"  AccessType: {policy.access_type.value if policy.access_type else '—'}")

    # -----------------------------------------------------------------------
    # 9. Download the insights and activity map report
    # -----------------------------------------------------------------------
    print("\n── Activity map report ──────────────────────────────────────────")
    report = client.reports.get_activity_map(format="json")
    print(f"  Download URL: {report.download_url}")
    if report.date_range:
        print(f"  Date range  : {report.date_range.start} to {report.date_range.end}")

    # -----------------------------------------------------------------------
    # 10. Clean up — policy, agent, and MCP server
    # -----------------------------------------------------------------------
    print("\n── Cleanup ──────────────────────────────────────────────────────")
    client.policies.set_state(policy.id, PolicyState.DISABLED)
    client.policies.delete(policy.id)
    print(f"  Policy deleted  : {policy.id}")

    client.agents.set_state(new_agent.id, "ACTIVE")
    print(f"  Agent activated : {new_agent.id}")
    client.agents.set_state(new_agent.id, "SUSPENDED")
    print(f"  Agent suspended : {new_agent.id}")
    client.agents.delete(new_agent.id)
    print(f"  Agent deleted   : {new_agent.id}")

    # Disable then delete the MCP server
    client.targets.set_mcp_server_state(mcp_server.id, "DISABLED")
    print(f"  MCP disabled   : {mcp_server.id}")
    client.targets.delete_mcp_server(mcp_server.id)
    print(f"  MCP deleted    : {mcp_server.id}")

    print("\nDone.")


if __name__ == "__main__":
    main()
