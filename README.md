# SecAI Python SDK

The **SecAI SDK** is the official Python client for the [Idira Secure AI API](secai-api.yaml).
It lets you register, govern, and control AI agents and their MCP (Model Context Protocol) server
targets from Python code or a command-line interface.

| Component                      | What it gives you                                              |
| ------------------------------ | -------------------------------------------------------------- |
| `secai` library                | Typed Python client for all 14 API endpoints                   |
| `secai-cli` CLI                | A command per endpoint; three output modes; scriptable         |
| Test suite                     | Live functional tests that drive the CLI against a real tenant |
| `sdk-quickstart/quickstart.py` | End-to-end runnable walkthrough                                |

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Python Library](#python-library)
   - [SecAIClient](#secaiclient)
   - [Agents Resource](#agents-resource)
   - [Targets Resource](#targets-resource)
   - [Data Models](#data-models)
   - [Error Handling](#error-handling)
5. [CLI Reference](#cli-reference)
   - [Global Options](#global-options)
   - [agents commands](#agents-commands)
   - [targets commands](#targets-commands)
   - [Output Formats](#output-formats)
6. [Running the Tests](#running-the-tests)
7. [Quickstart Example](#quickstart-example)
8. [Project Layout](#project-layout)

---

## Requirements

- Python 3.9 or later
- An Idira tenant URL and a valid Bearer JWT (see your Idira Identity Security portal)

---

## Installation

### Install from source (this repository)

```bash
git clone <repo-url>
cd secai-sdk

# Sync all dependencies (including dev and test extras)
uv sync --extra dev --extra test

# Run the CLI through uv
uv run secai-cli --help
```

### Install the CLI as a standalone tool

The quickest way to get `secai-cli` on your `$PATH` in its own isolated environment:

```bash
uv tool install .
secai-cli --help
```

Be sure to configure the environment variables in env-vars.sh and source that file to set the auth token before running commands.

### Add the library to a project

```bash
uv add <path-to>/secai
```

With optional extras:

```bash
uv add "secai[dev,test]"
```

The dev extras include the ruff linter, mypy type checker, and pre-commit git hook manager packages.
The test extras include pytest and pytest-httpx test driver packages.

> **Note:** When working from a source checkout, prefix every CLI invocation with `uv run`
> (e.g. `uv run secai-cli agents list`) so it uses the project's managed virtual environment.
> After a `uv tool install` the `secai-cli` entry point is on your `$PATH` and no prefix is needed.

---

## Configuration

The SDK reads configuration from environment variables or a `.env` file placed in the working directory.

| Variable           | CLI option            | Description                                                           |
| ------------------ | --------------------- | --------------------------------------------------------------------- |
| `SECAI_TENANT_URL` | `--tenant-url` / `-u` | Base URL of your Idira tenant, e.g. `https://mytenant.cyberark.cloud` |
| `SECAI_TOKEN`      | `--token` / `-t`      | Bearer JWT for authentication                                         |
| `SECAI_OUTPUT`     | `--output` / `-o`     | Default output format: `table` (default), `json`, `quiet`             |
| `SECAI_TIMEOUT`    | `--timeout`           | HTTP timeout in seconds (default: `30`)                               |

Example `.env` file:

```dotenv
SECAI_TENANT_URL=https://mytenant.cyberark.cloud
SECAI_TOKEN=eyJhbGciOiJSUzI1NiJ9...
```

> **Security note:** Bearer tokens are never written to disk, logs, or stdout by the SDK.
> Agent `clientSecret` values are printed once on registration — store them in a secrets manager immediately.

---

## Python Library

### SecAIClient

The central entry point. Import it and pass credentials either directly or via environment variables.

```python
from secai import SecAIClient

# Explicit credentials
client = SecAIClient(
    tenant_url="https://mytenant.cyberark.cloud",
    token="<bearer-jwt>",
)

# From environment (SECAI_TENANT_URL and SECAI_TOKEN)
client = SecAIClient()

# Use as a context manager (closes the HTTP pool automatically)
with SecAIClient() as client:
    agents = client.agents.list()
```

#### Constructor parameters

| Parameter    | Type          | Default             | Description                                          |
| ------------ | ------------- | ------------------- | ---------------------------------------------------- |
| `tenant_url` | `str \| None` | `$SECAI_TENANT_URL` | Tenant base URL                                      |
| `token`      | `str \| None` | `$SECAI_TOKEN`      | Bearer JWT                                           |
| `timeout`    | `float`       | `30.0`              | Per-request timeout in seconds                       |
| `verify_ssl` | `bool`        | `True`              | Disable only for local testing — never in production |

---

### Agents Resource

Access via `client.agents`.

#### `list() → list[Agent]`

Return all agents registered in the tenant.

```python
agents = client.agents.list()
for a in agents:
    print(a.id, a.name, a.status.state.value)
```

#### `register(request) → AgentWithCredentials`

Register a new agent. The returned object includes a one-time `credentials` block containing
`client_id`, `client_secret`, and `gateway_url` — save the secret immediately.

```python
from secai import RegisterAgentRequest

agent = client.agents.register(
    RegisterAgentRequest(
        name="Finance Copilot",
        type="COPILOT",
        description="AI agent for the finance dashboard.",
        owner="Finance",
        redirectCallbackUrls=["https://finance.example.com/oauth/callback"],
        tags={"environment": "production", "department": "finance"},
    )
)
print(agent.credentials.client_secret)  # ← save this now
```

#### `get(agent_id) → AgentWithCredentials`

Fetch full details for a single agent.

```python
agent = client.agents.get("a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12")
print(agent.status.state)
```

#### `edit(agent_id, request) → Agent`

Update mutable metadata. Fields not supplied are left unchanged.

```python
from secai import EditAgentRequest

updated = client.agents.edit(
    agent.id,
    EditAgentRequest(
        description="Updated description.",
        tags={"environment": "production", "team": "platform"},
    ),
)
```

#### `set_state(agent_id, state) → AgentStateResponse`

Transition an agent between `ACTIVE` and `SUSPENDED`. The state may be passed as a string
or as the `AgentState` enum.

```python
from secai import AgentState

client.agents.set_state(agent.id, AgentState.SUSPENDED)
client.agents.set_state(agent.id, "ACTIVE")  # string form also works
```

#### `delete(agent_id) → None`

Permanently delete an agent. The agent **must** be in `SUSPENDED` or `PENDING_CONFIGURATION`
state first; deleting an `ACTIVE` agent raises `ConflictError`.

```python
client.agents.set_state(agent.id, "SUSPENDED")
client.agents.delete(agent.id)
```

---

### Targets Resource

Access via `client.targets`.

#### `list_mcp_servers(*, cursor=None) → McpServerListResponse`

Return registered MCP servers. The response includes a `next_cursor` field for pagination.

```python
page = client.targets.list_mcp_servers()
for server in page.mcp_servers:
    print(server.id, server.name, server.state)

if page.next_cursor:
    page2 = client.targets.list_mcp_servers(cursor=page.next_cursor)
```

#### `register_mcp_server(request) → McpServerResponse`

Register a custom or predefined MCP server.

**Custom server (full configuration required):**

```python
from secai import (
    McpAuthMethod, McpAuthType, McpCategory,
    McpSource, McpSourceType, McpUpstream,
    RegisterMcpServerRequest,
)

server = client.targets.register_mcp_server(
    RegisterMcpServerRequest(
        source=McpSource(type=McpSourceType.CUSTOM),
        name="My Slack MCP Server",
        description="Custom Slack integration.",
        category=McpCategory.COMMUNICATION_AND_TEAM_CHAT,
        upstream=McpUpstream(url="https://slack-mcp.company.com/api"),
        authMethod=McpAuthMethod(
            type=McpAuthType.OAUTH2_1,
            authorizationServer="https://auth.company.com",
            JWKS="https://auth.company.com/.well-known/jwks.json",
        ),
        tags={"team": "engineering"},
    )
)
```

**Predefined server (from the catalog):**

```python
server = client.targets.register_mcp_server(
    RegisterMcpServerRequest(
        source=McpSource(
            type=McpSourceType.PREDEFINED,
            predefinedTargetId="3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8",
        ),
        name="Engineering Team Slack",
    )
)
```

#### `get_mcp_server(server_id) → McpServerResponse`

```python
server = client.targets.get_mcp_server("tgt-custom-slack-001")
```

#### `edit_mcp_server(server_id, request) → McpServerResponse`

Update `description`, `owners`, `tags`, and (for custom targets) `category`.
`name`, `authMethod`, and `upstream` are immutable after creation.

```python
from secai import EditMcpServerRequest

updated = client.targets.edit_mcp_server(
    server.id,
    EditMcpServerRequest(
        description="Updated description.",
        tags={"environment": "staging", "team": "R&D"},
    ),
)
```

#### `set_mcp_server_state(server_id, state) → McpServerResponse`

Toggle between `ENABLED` and `DISABLED`.

```python
from secai import McpState

client.targets.set_mcp_server_state(server.id, McpState.DISABLED)
client.targets.set_mcp_server_state(server.id, "ENABLED")  # string form works too
```

#### `delete_mcp_server(server_id) → None`

Delete a custom MCP server. Predefined servers cannot be deleted.

```python
client.targets.set_mcp_server_state(server.id, "DISABLED")
client.targets.delete_mcp_server(server.id)
```

#### `list_predefined_mcp_servers() → PredefinedMcpListResponse`

Browse the Idira Marketplace catalog of predefined MCP server templates.

```python
catalog = client.targets.list_predefined_mcp_servers()
for tmpl in catalog.targets:
    print(tmpl.id, tmpl.name, tmpl.category)
```

#### `get_predefined_mcp_server(predefined_id) → PredefinedMcpTarget`

```python
tmpl = client.targets.get_predefined_mcp_server("3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8")
print(tmpl.auth_method.type)
```

---

### Data Models

All models are Pydantic v2 `BaseModel` subclasses and support both snake_case attribute access
and `by_alias=True` serialization to the API's camelCase wire format.

#### Agent models

| Model                  | Purpose                                        |
| ---------------------- | ---------------------------------------------- |
| `RegisterAgentRequest` | Body for `POST /api/agents`                    |
| `EditAgentRequest`     | Body for `PATCH /api/agents/{id}`              |
| `Agent`                | Agent record (no credentials)                  |
| `AgentWithCredentials` | Agent record + `credentials` block             |
| `AgentCredentials`     | `client_id`, `client_secret`, `gateway_url`    |
| `AgentStatus`          | `state` (AgentState enum) + optional `message` |
| `AgentStateResponse`   | Response from state transition                 |
| `ListAgentsResponse`   | Paginated list of `Agent`                      |

#### Target models

| Model                       | Purpose                                                            |
| --------------------------- | ------------------------------------------------------------------ |
| `RegisterMcpServerRequest`  | Body for `POST /api/targets/mcp-servers`                           |
| `EditMcpServerRequest`      | Body for `PUT /api/targets/mcp-servers/{id}`                       |
| `McpServerResponse`         | Registered MCP server record                                       |
| `McpServerListResponse`     | Paginated list + `next_cursor`                                     |
| `PredefinedMcpTarget`       | Predefined template record                                         |
| `PredefinedMcpListResponse` | List of predefined templates                                       |
| `McpSource`                 | `type` (CUSTOM/PREDEFINED) + optional `predefinedTargetId/Version` |
| `McpUpstream`               | `url` of the upstream MCP endpoint                                 |
| `McpAuthMethod`             | `type` (OAUTH2.1/NONE), optional `authorizationServer`, `JWKS`     |

#### Enumerations

| Enum            | Values                                                                                                                                                      |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AgentState`    | `PENDING_CONNECTION`, `PENDING_CONFIGURATION`, `ACTIVE`, `SUSPENDED`, `CONNECTION_ERROR`, `ERROR`                                                           |
| `AgentType`     | `COPILOT`, `CLAUDE`, `CUSTOM`                                                                                                                               |
| `McpSourceType` | `CUSTOM`, `PREDEFINED`                                                                                                                                      |
| `McpAuthType`   | `OAUTH2_1`, `NONE`                                                                                                                                          |
| `McpState`      | `ENABLED`, `DISABLED`                                                                                                                                       |
| `McpCategory`   | `COMMUNICATION_AND_TEAM_CHAT`, `DEVELOPER_TOOLS_AND_SOURCE_CONTROL`, `ITSM_AND_INCIDENT_RESPONSE`, `KNOWLEDGE_BASES_AND_DOCS`, `WEB_AND_BROWSER_AUTOMATION` |

---

### Error Handling

All SDK methods raise a subclass of `SecAIError` on non-2xx responses. Every exception carries
`status_code`, `error_code`, `message`, and `description`.

```python
from secai import (
    SecAIClient,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitError,
    ServerError,
    SecAIError,
)

try:
    agent = client.agents.get("bad-id")
except NotFoundError as e:
    print(f"Not found: {e.message}")
except ConflictError as e:
    print(f"Conflict ({e.error_code}): {e.message}")
except AuthenticationError:
    print("Token is missing or expired.")
except RateLimitError:
    print("Rate limited — back off and retry.")
except SecAIError as e:
    print(f"Unexpected error {e.status_code}: {e}")
```

| Exception             | HTTP Status |
| --------------------- | ----------- |
| `AuthenticationError` | 401         |
| `AuthorizationError`  | 403         |
| `NotFoundError`       | 404         |
| `ConflictError`       | 409         |
| `ValidationError`     | 422         |
| `RateLimitError`      | 429         |
| `ServerError`         | 5xx         |
| `UnexpectedError`     | Any other   |

---

## CLI Reference

```bash
secai-cli [OPTIONS] COMMAND [ARGS]...

Options:
  --help   Show this message and exit.

Commands:
  agents   Agent inventory and lifecycle management.
  targets  MCP server target registry management.
```

### Global Options

Set once via environment variables so you don't repeat them on every command:

```bash
export SECAI_TENANT_URL=https://mytenant.cyberark.cloud
export SECAI_TOKEN=eyJhbGciOiJSUzI1NiJ9...
export SECAI_OUTPUT=json   # optional: table (default) | json | quiet
```

---

### agents commands

#### `agents list`

```bash
secai-cli agents list [--output TABLE|JSON|QUIET]
```

List all agents. The table view colour-codes lifecycle states
(green=ACTIVE, yellow=SUSPENDED, red=ERROR).

```bash
secai-cli agents list
secai-cli agents list --output json | jq '.[].id'
```

---

#### `agents register`

```bash
secai-cli agents register \
  --name      <name>         Required. Alphanumeric, spaces, hyphens.
  --type      <type>         Required. COPILOT | CLAUDE | CUSTOM.
  --description <text>       Optional.
  --owner     <team>         Optional.
  --callback-url <url>       Repeatable. Must start with https://.
  --tag       KEY=VALUE      Repeatable. Up to 10 tags.
  --owner-id  <user-id>      Repeatable.
  --output    table|json|quiet
```

```bash
secai-cli agents register \
  --name "Finance Copilot" \
  --type COPILOT \
  --description "Finance dashboard agent" \
  --owner "Finance" \
  --callback-url https://finance.example.com/oauth/callback \
  --tag environment=production \
  --tag department=finance
```

> The `clientSecret` is printed once. Pipe to a secrets manager immediately in automated flows:
>
> ```bash
> secai-cli agents register --name MyAgent --type COPILOT --output json \
>   | jq -r '.credentials.clientSecret' \
>   | vault kv put secret/myagent clientSecret=-
> ```

---

#### `agents get <agent-id>`

```bash
secai-cli agents get <agent-id> [--output TABLE|JSON|QUIET]
```

```bash
secai-cli agents get a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12
secai-cli agents get a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 --output json
```

---

#### `agents edit <agent-id>`

```bash
secai-cli agents edit <agent-id> \
  [--name <name>] [--description <text>] [--owner <team>]
  [--tag KEY=VALUE ...]   # Replaces all existing tags
  [--output TABLE|JSON|QUIET]
```

```bash
secai-cli agents edit a8f9c2d1 --description "New description" --tag env=staging
```

---

#### `agents set-state <agent-id> <state>`

State must be `ACTIVE` or `SUSPENDED`.

```bash
secai-cli agents set-state a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 SUSPENDED
secai-cli agents set-state a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 ACTIVE
```

---

#### `agents delete <agent-id>`

`--confirm` is required. The agent must be `SUSPENDED` first.

```bash
secai-cli agents set-state a8f9c2d1 SUSPENDED
secai-cli agents delete a8f9c2d1 --confirm
```

---

### targets commands

#### `targets list`

```bash
secai-cli targets list [--cursor <cursor>] [--output TABLE|JSON|QUIET]
```

```bash
secai-cli targets list
secai-cli targets list --output json | jq '.mcpServers[].name'
```

---

#### `targets register`

```bash
secai-cli targets register \
  --source CUSTOM|PREDEFINED        Required.
  --name <name>                     Required for CUSTOM; optional for PREDEFINED.
  --description <text>
  --category <category>             Required for CUSTOM. See category list below.
  --url <upstream-url>              Required for CUSTOM.
  --auth-type OAUTH2.1|NONE         Required for CUSTOM.
  --auth-server <url>               Optional. OAuth 2.1 authorization server.
  --jwks <url>                      Optional. JWKS endpoint for token validation.
  --predefined-id <uuid>            Required for PREDEFINED.
  --predefined-version <int>        Optional (defaults to latest).
  --tag KEY=VALUE                   Repeatable.
  --owner-id <user-id>              Repeatable.
  --output TABLE|JSON|QUIET
```

**Custom server:**

```bash
secai-cli targets register \
  --source CUSTOM \
  --name "My Slack MCP" \
  --category COMMUNICATION_AND_TEAM_CHAT \
  --url https://slack-mcp.company.com/api \
  --auth-type OAUTH2.1 \
  --auth-server https://auth.company.com \
  --jwks https://auth.company.com/.well-known/jwks.json \
  --tag team=engineering
```

**Predefined server from catalog:**

```bash
secai-cli targets register \
  --source PREDEFINED \
  --predefined-id 3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8 \
  --name "Engineering Slack"
```

**Valid category values:**

| Value                                | Description                 |
| ------------------------------------ | --------------------------- |
| `COMMUNICATION_AND_TEAM_CHAT`        | Slack, Teams, etc.          |
| `DEVELOPER_TOOLS_AND_SOURCE_CONTROL` | GitHub, GitLab, etc.        |
| `ITSM_AND_INCIDENT_RESPONSE`         | Jira, ServiceNow, etc.      |
| `KNOWLEDGE_BASES_AND_DOCS`           | Confluence, Notion, etc.    |
| `WEB_AND_BROWSER_AUTOMATION`         | Web scraping, browser tools |

---

#### `targets get <id>`

```bash
secai-cli targets get tgt-custom-slack-001
secai-cli targets get tgt-custom-slack-001 --output json
```

---

#### `targets edit <id>`

```bash
secai-cli targets edit <id> \
  [--description <text>]
  [--category <category>]    # Custom targets only
  [--tag KEY=VALUE ...]       # Replaces all existing tags
  [--owner-id <user-id> ...]
  [--output TABLE|JSON|QUIET]
```

```bash
secai-cli targets edit tgt-custom-slack-001 \
  --description "Updated description" \
  --tag env=staging \
  --tag team=platform
```

---

#### `targets set-state <id> <state>`

State must be `ENABLED` or `DISABLED`.

```bash
secai-cli targets set-state tgt-custom-slack-001 DISABLED
secai-cli targets set-state tgt-custom-slack-001 ENABLED
```

---

#### `targets delete <id>`

`--confirm` required. Predefined targets cannot be deleted.

```bash
secai-cli targets set-state tgt-custom-slack-001 DISABLED
secai-cli targets delete tgt-custom-slack-001 --confirm
```

---

#### `targets list-predefined`

```bash
secai-cli targets list-predefined
secai-cli targets list-predefined --output json | jq '.targets[].name'
```

---

#### `targets get-predefined <id>`

```bash
secai-cli targets get-predefined 3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8
```

---

### Output Formats

| Format  | How to select                           | Best for                                     |
| ------- | --------------------------------------- | -------------------------------------------- |
| `table` | Default / `--output table`              | Interactive terminal use; color-coded states |
| `json`  | `--output json` / `SECAI_OUTPUT=json`   | Piping to `jq`, integration scripts, CI      |
| `quiet` | `--output quiet` / `SECAI_OUTPUT=quiet` | Capturing IDs in shell variables             |

**Capture an ID in a shell script:**

```bash
AGENT_ID=$(secai-cli agents register --name "Deploy Bot" --type CUSTOM --output quiet)
echo "Created agent: $AGENT_ID"
```

**Exit codes:**

| Code | Meaning            |
| ---- | ------------------ |
| `0`  | Success            |
| `1`  | Client error (4xx) |
| `2`  | Server error (5xx) |

---

## Running the Tests

The test suite makes real API calls against a live tenant. Configure credentials first:

```bash
cp .env.example .env.test   # or set env vars directly
# Edit .env.test with your SECAI_TENANT_URL and SECAI_TOKEN
```

Install test dependencies and run:

```bash
pip install "secai[test]"

# Run everything
pytest tests/ -v --tb=short

# Agents only
pytest tests/test_agents_cli.py -v

# Targets only
pytest tests/test_targets_cli.py -v

# Run with explicit credentials (overrides .env.test)
SECAI_TENANT_URL=https://my.cyberark.cloud \
SECAI_TOKEN=$(cat my_jwt.txt) \
pytest tests/ -v
```

**What the tests do:**

- Session-scoped fixtures in `conftest.py` register one test agent and one test MCP server at
  the start of the session, then delete them at the end.
- Every test resource name is prefixed with `test-secai-sdk-` for easy identification.
- Each test class is self-contained; failing one class does not block others.
- Negative-path tests verify that the correct HTTP error code appears on stderr.

---

## Quickstart Example

The file `examples/quickstart.py` demonstrates the complete workflow end-to-end.

```bash
export SECAI_TENANT_URL=https://mytenant.cyberark.cloud
export SECAI_TOKEN=$(cat my_jwt.txt)

python examples/quickstart.py
```

Expected output (abbreviated):

```plaintext
── Existing agents ──────────────────────────────────────────────
  a8f9c2d1  IT Operations Agent          ACTIVE
  b9e8d7c6  Sales Bot                    SUSPENDED

── Registering agent ────────────────────────────────────────────
  Registered : f1e2d3c4-...
  Name       : SDK Quickstart Agent
  State      : PENDING_CONNECTION
  Client ID  : agent-xxx-client
  Secret     : s3cr3t-...  ← store securely; shown once
  Gateway    : https://aigw.cyberark.cloud

── Registering MCP server ───────────────────────────────────────
  Registered : tgt-sdk-...
  State      : ENABLED
  Gateway    : https://aigw.cyberark.cloud/mcp/sdk

── Predefined MCP catalog ───────────────────────────────────────
  3f4e5d6c  Slack MCP Server               COMMUNICATION_AND_TEAM_CHAT
  5a6b7c8d  GitHub MCP Server              DEVELOPER_TOOLS_AND_SOURCE_CONTROL

── Cleanup ──────────────────────────────────────────────────────
  Agent suspended: f1e2d3c4-...
  Agent deleted  : f1e2d3c4-...
  MCP disabled   : tgt-sdk-...
  MCP deleted    : tgt-sdk-...

Done.
```

---

## Project Layout

```plaintext
sai-api2/
├── pyproject.toml              # Package metadata and dependencies
├── secai-api.yaml              # OpenAPI 3.0 source spec
├── secai-sdk-prd.docx          # Product requirements document
│
├── secai/                      # SDK library
│   ├── __init__.py             # Public API surface
│   ├── client.py               # SecAIClient and _BaseClient
│   ├── agents.py               # AgentsResource (6 methods)
│   ├── targets.py              # TargetsResource (8 methods)
│   ├── models.py               # Pydantic v2 request/response models
│   ├── exceptions.py           # SecAIError hierarchy
│   └── cli/
│       ├── __init__.py
│       ├── main.py             # Typer app + sub-group registration
│       ├── agents_cmds.py      # agents list/register/get/edit/delete/set-state
│       └── targets_cmds.py     # targets list/register/get/edit/delete/set-state
│                               #         list-predefined/get-predefined
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Session fixtures (live agent + MCP server)
│   ├── test_agents_cli.py      # 14 agent test cases (positive + negative)
│   └── test_targets_cli.py     # 16 target test cases (positive + negative)
│
└── examples/
    └── quickstart.py           # Annotated end-to-end walkthrough
```

---

## API Endpoint Coverage

| Method | Endpoint                                   | SDK method                                       | CLI command                                |
| ------ | ------------------------------------------ | ------------------------------------------------ | ------------------------------------------ |
| GET    | `/api/agents`                              | `client.agents.list()`                           | `secai-cli agents list`                    |
| POST   | `/api/agents`                              | `client.agents.register(req)`                    | `secai-cli agents register`                |
| GET    | `/api/agents/{id}`                         | `client.agents.get(id)`                          | `secai-cli agents get <id>`                |
| PATCH  | `/api/agents/{id}`                         | `client.agents.edit(id, req)`                    | `secai-cli agents edit <id>`               |
| DELETE | `/api/agents/{id}`                         | `client.agents.delete(id)`                       | `secai-cli agents delete <id> --confirm`   |
| POST   | `/api/agents/{id}/state`                   | `client.agents.set_state(id, state)`             | `secai-cli agents set-state <id> <state>`  |
| GET    | `/api/targets/mcp-servers`                 | `client.targets.list_mcp_servers()`              | `secai-cli targets list`                   |
| POST   | `/api/targets/mcp-servers`                 | `client.targets.register_mcp_server(req)`        | `secai-cli targets register`               |
| GET    | `/api/targets/mcp-servers/{id}`            | `client.targets.get_mcp_server(id)`              | `secai-cli targets get <id>`               |
| PUT    | `/api/targets/mcp-servers/{id}`            | `client.targets.edit_mcp_server(id, req)`        | `secai-cli targets edit <id>`              |
| DELETE | `/api/targets/mcp-servers/{id}`            | `client.targets.delete_mcp_server(id)`           | `secai-cli targets delete <id> --confirm`  |
| POST   | `/api/targets/mcp-servers/{id}/state`      | `client.targets.set_mcp_server_state(id, state)` | `secai-cli targets set-state <id> <state>` |
| GET    | `/api/targets/predefined/mcp-servers`      | `client.targets.list_predefined_mcp_servers()`   | `secai-cli targets list-predefined`        |
| GET    | `/api/targets/predefined/mcp-servers/{id}` | `client.targets.get_predefined_mcp_server(id)`   | `secai-cli targets get-predefined <id>`    |

---

## License

Apache 2.0 — see [LICENSE](http://www.apache.org/licenses/LICENSE-2.0.html).
