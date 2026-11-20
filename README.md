# SecAI Python SDK

[![CI](https://github.com/idirademos/idira-secai-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/idirademos/idira-secai-sdk/actions/workflows/ci.yml)

The **SecAI SDK** is the official Python client for the [Idira Secure AI API](secai-api.yaml).
It lets you register, govern, and control AI agents and their MCP (Model Context Protocol) server
targets from Python code or a command-line interface.

> **Current version: 0.2.0.** This release includes breaking API changes versus `0.1.0` — see
> [CHANGELOG.md](CHANGELOG.md) before upgrading.

| Component                      | What it gives you                                                                |
| ------------------------------ | -------------------------------------------------------------------------------- |
| `secai` library                | Typed Python client for all Agents, Targets, Policies, and Reports API endpoints |
| `secai-cli` CLI                | A command per endpoint; three output modes; scriptable                           |
| Test suite                     | Live functional tests that drive the CLI against a real tenant                   |
| `sdk-quickstart/quickstart.py` | End-to-end runnable walkthrough                                                  |

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Credential Storage](#credential-storage)
5. [Resilience](#resilience)
6. [Python Library](#python-library)
   - [SecAIClient](#secaiclient)
   - [Agents Resource](#agents-resource)
   - [Targets Resource](#targets-resource)
   - [Policies Resource](#policies-resource)
   - [Reports Resource](#reports-resource)
   - [Data Models](#data-models)
   - [Error Handling](#error-handling)
7. [CLI Reference](#cli-reference)
   - [Global Options](#global-options)
   - [login / logout / whoami](#login--logout--whoami)
   - [agents commands](#agents-commands)
   - [targets commands](#targets-commands)
   - [policies commands](#policies-commands)
   - [reports commands](#reports-commands)
   - [Output Formats](#output-formats)
8. [Running the Tests](#running-the-tests)
9. [Quickstart Example](#quickstart-example)
10. [Project Layout](#project-layout)

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

`keyring` (used to store `secai-cli login` credentials in the OS keychain/credential store) is a
required core dependency, so it's installed automatically with the package — no extra needed. See
[Credential Storage](#credential-storage) below for how the actual backend is selected at runtime.

> **Note:** When working from a source checkout, prefix every CLI invocation with `uv run`
> (e.g. `uv run secai-cli agents list`) so it uses the project's managed virtual environment.
> After a `uv tool install` the `secai-cli` entry point is on your `$PATH` and no prefix is needed.

---

## Configuration

The SDK reads configuration from environment variables or a `.env` file placed in the working directory.

| Variable             | CLI option                        | Description                                                                                                                |
| -------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `SECAI_TENANT_URL`   | `--tenant-url` / `-u`             | Base URL of your Idira tenant, e.g. `https://mytenant.cyberark.cloud`                                                      |
| `SECAI_TOKEN`        | `--token` / `-t`                  | Bearer JWT for authentication                                                                                              |
| `SECAI_OUTPUT`       | `--output` / `-o`                 | Default output format: `table` (default), `json`, `quiet`                                                                  |
| `SECAI_TIMEOUT`      | `--timeout`                       | HTTP timeout in seconds (default: `30`)                                                                                    |
| `SECAI_MAX_RETRIES`  | —                                 | Max automatic retries for transient HTTP failures (default: `3`, see [Resilience](#resilience))                            |
| `SECAI_CONFIG_DIR`   | —                                 | Override the directory used to cache `secai-cli login` credentials (default: `~/.config/secai`)                            |
| `SECAI_NO_KEYRING`   | —                                 | Set to force the plaintext credentials file even when the OS keyring works (see [Credential Storage](#credential-storage)) |
| `IDIRA_IDENTITY_URL` | `secai-cli login --identity-url`  | CyberArk Identity API base URL, used by `secai-cli login`'s OAuth2 exchange                                                |
| `IDIRA_ADMIN_USER`   | `secai-cli login --client-id`     | OAuth service account client ID, used by `secai-cli login`'s OAuth2 exchange                                               |
| `IDIRA_ADMIN_PWD`    | `secai-cli login --client-secret` | OAuth service account client secret, used by `secai-cli login`'s OAuth2 exchange                                           |

Example `.env` file:

```dotenv
SECAI_TENANT_URL=https://mytenant.cyberark.cloud
SECAI_TOKEN=eyJhbGciOiJSUzI1NiJ9...
```

> **Security note:** Bearer tokens are never written to disk, logs, or stdout by the SDK itself.
> The CLI's `secai-cli login` command is the one exception — it caches the resolved tenant
> URL/token (see [Credential Storage](#credential-storage) for exactly where) so you don't need
> to export env vars every session. By default `login` never requires you to paste a raw JWT: it
> exchanges a service account's `client_id`/`client_secret` for a token via OAuth2
> `client_credentials` (see [login / logout / whoami](#login--logout--whoami)). Explicit
> `SECAI_TENANT_URL`/`SECAI_TOKEN` env vars always take precedence over a cached login (useful
> for CI).
> **When OAuth was used to log in**, the cache additionally stores the `identity_url`/`client_id`/
> `client_secret` so the CLI can silently re-authenticate when a cached token expires (see
> [Resilience](#resilience)) — this means the cached entry is then at least as sensitive as
> the underlying service-account secret, not just a short-lived token. Logging in with `--token`
> avoids this (only the token itself is cached, with no automatic refresh).
> Agent `clientSecret` values are printed once on registration — store them in a secrets manager immediately.

---

## Credential Storage

`secai-cli login` stores its cache in the OS-native secret store when possible, falling back to
a plaintext file otherwise — there's no platform-specific configuration needed, it's detected
automatically on every `login`/`whoami`/`logout`:

1. **OS keyring** (preferred): `keyring` is a required dependency, so it's always installed.
   macOS Keychain and Windows Credential Locker work out of the box. Linux requires a running
   Secret Service daemon (GNOME Keyring, KWallet) with an unlocked session — true on most Linux
   desktops, but typically not available on headless servers, SSH-only boxes, or CI
   containers.
2. **Plaintext file** (fallback): `~/.config/secai/credentials.json`, mode `0600`
   (owner-read/write only). Used automatically when no keyring backend is usable on the current
   machine (e.g. headless Linux), or `SECAI_NO_KEYRING` is set. Override the directory with
   `SECAI_CONFIG_DIR`.

`secai-cli login` prints which backend it used; `secai-cli whoami` shows it too (`Source:`
line). A plaintext cache left over from a machine/session where no keyring backend was available
is opportunistically migrated into the keyring (and the file deleted) the next time any command
reads it on a machine where one becomes usable — no need to run `login` again. `secai-cli logout`
clears both locations. Set `SECAI_NO_KEYRING=1` to always use the plaintext file even on a machine
where the keyring would otherwise work.

---

## Resilience

Both the `SecAIClient` and the CLI automatically retry transient HTTP failures and can
silently refresh an expired token:

- **Retry/backoff** — connection errors, timeouts, and HTTP `429`/`502`/`503`/`504` responses
  are retried regardless of method; a plain `500` is retried only for `GET` requests (write
  requests may have partially applied server-side, so they are not blindly retried). Retries use
  exponential backoff with jitter, honoring a `Retry-After` header when the server provides one.
  Configure the retry budget with the `max_retries` constructor parameter or the
  `SECAI_MAX_RETRIES` env var (default `3`; set to `0` to disable retries).
- **Automatic token refresh on 401** — if a request returns `401 Unauthorized`, the client will
  make a single attempt to obtain a fresh token and retry the request once before giving up. In
  the Python library this requires passing a `token_refresher` callable to `SecAIClient`; the CLI
  wires this up automatically whenever you're authenticated via `secai-cli login` or
  `IDIRA_IDENTITY_URL`/`IDIRA_ADMIN_USER`/`IDIRA_ADMIN_PWD` env vars, preferring the env vars
  (never touches disk) over the cached login when both are available. `secai-cli whoami` shows
  whether auto-refresh is active for your current session.

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

| Parameter         | Type                        | Default             | Description                                                        |
| ----------------- | --------------------------- | ------------------- | ------------------------------------------------------------------ |
| `tenant_url`      | `str \| None`               | `$SECAI_TENANT_URL` | Tenant base URL                                                    |
| `token`           | `str \| None`               | `$SECAI_TOKEN`      | Bearer JWT                                                         |
| `timeout`         | `float`                     | `30.0`              | Per-request timeout in seconds                                     |
| `verify_ssl`      | `bool`                      | `True`              | Disable only for local testing — never in production               |
| `max_retries`     | `int`                       | `3`                 | Max retries for transient failures (see [Resilience](#resilience)) |
| `backoff_factor`  | `float`                     | `0.5`               | Base delay multiplier for exponential backoff                      |
| `max_backoff`     | `float`                     | `8.0`               | Cap on the computed backoff delay, in seconds                      |
| `token_refresher` | `Callable[[], str] \| None` | `None`              | Optional callback invoked once to obtain a new token after a `401` |

---

### Agents Resource

Access via `client.agents`.

#### `list(*, page_size=None, continuation_token=None) → ListAgentsResponse`

Return a page of agents registered in the tenant (cursor-paginated).

```python
page = client.agents.list(page_size=50)
for a in page.agents:
    print(a.id, a.name, a.status.state.value)

if page.page_info and page.page_info.continuation_token:
    next_page = client.agents.list(continuation_token=page.page_info.continuation_token)
```

#### `iter_all(*, page_size=None) → Iterator[Agent]`

Yield every agent in the tenant, transparently paging through `list()` under the hood.

```python
for agent in client.agents.iter_all(page_size=100):
    print(agent.id, agent.name)
```

#### `search(request) → ListAgentsResponse`

Search agents with a filter expression. Supported fields are `id`, `type`, `origin_id`, and `spiffeId`.

```python
from secai import SearchAgentsRequest

result = client.agents.search(
    SearchAgentsRequest(filter="type in [AWS_BEDROCK] and origin_id is null", pageSize=100)
)
```

#### `summary() → AgentsSummary`

Counts of agents by type and connection status, plus SPIFFE/JWT agent counts.

```python
summary = client.agents.summary()
print(summary.spiffe_count, summary.jwt_count)
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

To register a SPIFFE or JWT-authenticated agent, pass `authn_descriptors`:

```python
from secai import AuthnDescriptorInput, AuthnDescriptorType

agent = client.agents.register(
    RegisterAgentRequest(
        name="spiffe-agent",
        type="CUSTOM",
        redirectCallbackUrls=["https://example.org/callback"],
        authnDescriptors=[
            AuthnDescriptorInput(
                type=AuthnDescriptorType.JWT_SVID,
                subType="built-in-jwks",
                data={"sub": "spiffe://example.org/ns/prod/agent-a"},
            )
        ],
    )
)
```

#### `get(agent_id) → AgentWithCredentials`

Fetch full details for a single agent.

```python
agent = client.agents.get("a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12")
print(agent.status.state)
```

#### `edit(agent_id, request) → Agent | None`

Update mutable metadata (`name`, `owners`, `tags`, `description`, `authn_descriptors`). Fields not
supplied are left unchanged. Returns `None` if the request exactly matches the stored agent
(HTTP 204 — nothing is written or audited).

```python
from secai import EditAgentRequest

updated = client.agents.edit(
    agent.id,
    EditAgentRequest(
        description="Updated description.",
        tags={"environment": "production", "team": "platform"},
    ),
)
if updated is None:
    print("No changes — request matched the stored agent")
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

Permanently delete an agent. The agent **must** be in `SUSPENDED` or `PENDING_CONNECTION`
state first; deleting an `ACTIVE` agent raises `ConflictError`.

```python
client.agents.set_state(agent.id, "SUSPENDED")
client.agents.delete(agent.id)
```

#### `list_authn_descriptors(agent_id) → list[AuthnDescriptorOutput]`

```python
descriptors = client.agents.list_authn_descriptors(agent.id)
```

#### `delete_authn_descriptor(agent_id, descriptor_id) → None`

```python
client.agents.delete_authn_descriptor(agent.id, descriptors[0].id)
```

---

### Targets Resource

Access via `client.targets`.

#### `list_mcp_servers(*, page_size=None, next_cursor=None) → McpServerListResponse`

Return registered MCP servers (cursor-paginated).

```python
page = client.targets.list_mcp_servers(page_size=50)
for server in page.mcp_servers:
    print(server.id, server.name, server.state)

if page.next_cursor:
    page2 = client.targets.list_mcp_servers(next_cursor=page.next_cursor)
```

#### `iter_all_mcp_servers(*, page_size=None) → Iterator[McpServerResponse]`

Yield every registered MCP server, transparently paging through `list_mcp_servers()` under the hood.

```python
for server in client.targets.iter_all_mcp_servers(page_size=100):
    print(server.id, server.name)
```

#### `register_mcp_server(request) → McpServerResponse`

Register a custom or predefined MCP server. The request type now depends on the source: pass a
`RegisterCustomMcpServerRequest` for a CUSTOM target or a `RegisterPredefinedMcpServerRequest` to
instantiate a catalog template.

**Custom server (full configuration required):**

```python
from secai import (
    McpAuthMethod, McpAuthType, McpCategory,
    McpSource, McpSourceType, McpUpstream,
    RegisterCustomMcpServerRequest,
)

server = client.targets.register_mcp_server(
    RegisterCustomMcpServerRequest(
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
from secai import RegisterPredefinedMcpServerRequest

server = client.targets.register_mcp_server(
    RegisterPredefinedMcpServerRequest(
        source=McpSource(
            type=McpSourceType.PREDEFINED,
            predefinedTargetId="3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8",
        ),
    )
)
```

#### `get_mcp_server(server_id) → McpServerResponse`

```python
server = client.targets.get_mcp_server("tgt-custom-slack-001")
```

#### `edit_mcp_server(server_id, request) → McpServerResponse`

Update `description`, `owners`, `tags`, and (for custom targets) `category`.
`name` and `upstream` are immutable after creation. For `API_KEY`/`PAT` targets, pass
`auth_method` (an `AuthMethodUpdate`) to rotate stored headers/API keys — OAuth/NONE targets
cannot change their auth method after registration.

```python
from secai import ApiKeyEntry, AuthMethodUpdate, EditMcpServerRequest

updated = client.targets.edit_mcp_server(
    server.id,
    EditMcpServerRequest(
        description="Updated description.",
        tags={"environment": "staging", "team": "R&D"},
        authMethod=AuthMethodUpdate(apiKeys=[ApiKeyEntry(apiKey="new-secret-key")]),
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

#### `get_predefined_mcp_server(predefined_id) → PredefinedMcpTargetDetail`

Returns the template plus its `tools` list (unlike the summary objects in
`list_predefined_mcp_servers`).

```python
tmpl = client.targets.get_predefined_mcp_server("3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8")
print(tmpl.auth_method.type)
for tool in tmpl.tools:
    print(tool.name, tool.description)
```

---

### Policies Resource

Access via `client.policies`. Access policies govern which agents may act `ON_BEHALF_OF` a user
or `AUTONOMOUS`ly, and under what conditions (agent/user/resource/match rules).

#### `list(*, page_size=None, cursor=None) → ListPolicyOutput`

```python
page = client.policies.list(page_size=50)
for policy in page.policies:
    print(policy.id, policy.name, policy.state)
```

#### `iter_all(*, page_size=None) → Iterator[PolicyOutput]`

Yield every access policy in the tenant, transparently paging through `list()` under the hood.

```python
for policy in client.policies.iter_all(page_size=100):
    print(policy.id, policy.name)
```

#### `create(request) → PolicyOutput`

```python
from secai import Condition, ConditionGroup, ConditionOp, PolicyAccessType, PolicyInput

policy = client.policies.create(
    PolicyInput(
        name="Finance agent on-behalf-of policy",
        description="Allows the finance agent to act on behalf of finance users.",
        accessType=PolicyAccessType.ON_BEHALF_OF,
        user=ConditionGroup(conditions=[Condition(op=ConditionOp.IN, key="group", value=["finance"])]),
        agent=ConditionGroup(conditions=[Condition(op=ConditionOp.IN, key="id", value=[agent.id])]),
    )
)
```

`AUTONOMOUS` policies must omit `user`; `ON_BEHALF_OF` policies must supply a non-empty `user`
condition group — this is enforced client-side before the request is sent.

#### `get(policy_id) → PolicyOutput`

```python
policy = client.policies.get(policy.id)
```

#### `update(policy_id, request) → PolicyOutput`

```python
from secai import PolicyUpdate

updated = client.policies.update(policy.id, PolicyUpdate(description="Updated description."))
```

#### `delete(policy_id) → None`

```python
client.policies.delete(policy.id)
```

#### `set_state(policy_id, state) → PolicyStateResponse`

Toggle between `ENABLED` and `DISABLED`.

```python
from secai import PolicyState

client.policies.set_state(policy.id, PolicyState.DISABLED)
```

---

### Reports Resource

Access via `client.reports`.

#### `get_activity_map(*, format=None) → ActivityMapReport`

Request a short-lived presigned download URL for the tenant's activity-map report. `format` is
`"html"` (default) or `"json"`; the response itself only contains the URL and covered date range
— issue a follow-up `GET` to `download_url` to retrieve the file.

```python
report = client.reports.get_activity_map(format="json")
print(report.download_url)
print(report.date_range.start, report.date_range.end)
```

---

### Data Models

All models are Pydantic v2 `BaseModel` subclasses and support both snake_case attribute access
and `by_alias=True` serialization to the API's camelCase wire format.

#### Agent models

| Model                   | Purpose                                                      |
| ----------------------- | ------------------------------------------------------------ |
| `RegisterAgentRequest`  | Body for `POST /api/agents`                                  |
| `EditAgentRequest`      | Body for `PUT /api/agents/{id}`                              |
| `SearchAgentsRequest`   | Body for `POST /api/agents/search`                           |
| `Agent`                 | Agent record (no credentials)                                |
| `AgentWithCredentials`  | Agent record + `credentials` block                           |
| `AgentCredentials`      | `client_id`, `client_secret`, `gateway_url`                  |
| `AgentStatus`           | `state` (AgentState enum) + optional `message`               |
| `AgentStateResponse`    | Response from state transition                               |
| `ListAgentsResponse`    | Cursor-paginated list of `Agent` + `page_info`/`total_count` |
| `PageInfo`              | `page_size`, `continuation_token`                            |
| `AgentsSummary`         | Counts by type/status + `spiffe_count`/`jwt_count`           |
| `AuthnDescriptorInput`  | Authn descriptor supplied on register/edit                   |
| `AuthnDescriptorOutput` | Authn descriptor returned by the API                         |

#### Target models

| Model                                | Purpose                                                                |
| ------------------------------------ | ---------------------------------------------------------------------- |
| `RegisterCustomMcpServerRequest`     | Body for `POST /api/targets/mcp-servers` with `source.type=CUSTOM`     |
| `RegisterPredefinedMcpServerRequest` | Body for `POST /api/targets/mcp-servers` with `source.type=PREDEFINED` |
| `EditMcpServerRequest`               | Body for `PUT /api/targets/mcp-servers/{id}`                           |
| `AuthMethodUpdate`                   | `EditMcpServerRequest.auth_method` — rotates API_KEY/PAT credentials   |
| `McpServerResponse`                  | Registered MCP server record                                           |
| `McpServerListResponse`              | Cursor-paginated list + `next_cursor`                                  |
| `PredefinedMcpTarget`                | Predefined template summary record                                     |
| `PredefinedMcpTargetDetail`          | Predefined template + `tools` list                                     |
| `PredefinedMcpListResponse`          | List of predefined template summaries                                  |
| `McpSource`                          | `type` (CUSTOM/PREDEFINED) + optional `predefinedTargetId/Version`     |
| `McpUpstream`                        | `url` of the upstream MCP endpoint                                     |
| `McpAuthMethod`                      | `type` (OAUTH2.1/NONE/API_KEY/PAT) + type-specific fields              |
| `UpstreamHeader`                     | `name` + `valueTemplate` forwarded header (API_KEY/PAT)                |
| `ApiKeyEntry`                        | Write-only `apiKey` entry on requests                                  |
| `ApiKeyMetadata`                     | `createdAt`-only entry echoed back on responses (never the secret)     |

#### Policy models

| Model                 | Purpose                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `PolicyInput`         | Body for `POST /api/policies`                                        |
| `PolicyUpdate`        | Body for `PUT /api/policies/{id}` (all fields optional)              |
| `PolicyOutput`        | Policy record                                                        |
| `ListPolicyOutput`    | Cursor-paginated list of `PolicyOutput`                              |
| `PolicyStateResponse` | Response from a policy state transition                              |
| `Condition`           | A single `op`/`key`/`value` match rule                               |
| `ConditionGroup`      | `conditions` list (max 1 item) for `agent`/`user`/`resource`/`match` |

#### Report models

| Model                  | Purpose                                                   |
| ---------------------- | --------------------------------------------------------- |
| `ActivityMapReport`    | `download_url` + `date_range` for the activity-map report |
| `ActivityMapDateRange` | `start`/`end` date strings covered by the report          |

#### Enumerations

| Enum                  | Values                                                                                                                                                                                                                                                                                                                              |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AgentState`          | `PENDING_CONNECTION`, `ACTIVE`, `SUSPENDED`, `CONNECTION_ERROR`                                                                                                                                                                                                                                                                     |
| `AgentType`           | `COPILOT`, `CLAUDE`, `CUSTOM`                                                                                                                                                                                                                                                                                                       |
| `AuthnDescriptorType` | `jwt`, `jwt-svid`, `oauth2`                                                                                                                                                                                                                                                                                                         |
| `McpSourceType`       | `CUSTOM`, `PREDEFINED`                                                                                                                                                                                                                                                                                                              |
| `McpAuthType`         | `OAUTH2_1` (`"OAUTH2.1"`), `NONE`, `API_KEY`, `PAT`                                                                                                                                                                                                                                                                                 |
| `McpState`            | `ENABLED`, `DISABLED`                                                                                                                                                                                                                                                                                                               |
| `McpCategory`         | `COMMUNICATION_AND_TEAM_CHAT`, `EMAIL_AND_SCHEDULING`, `KNOWLEDGE_BASES_AND_DOCS`, `FILE_STORAGE_AND_CONTENT_REPOS`, `DEVELOPER_TOOLS_AND_SOURCE_CONTROL`, `DATABASES_AND_DATA_STORES`, `OBSERVABILITY_MONITORING_AND_TELEMETRY`, `ITSM_AND_INCIDENT_RESPONSE`, `WEB_AND_BROWSER_AUTOMATION`, `CLOUD_AND_INFRASTRUCTURE_OPERATIONS` |
| `PolicyState`         | `ENABLED`, `DISABLED`                                                                                                                                                                                                                                                                                                               |
| `PolicyAccessType`    | `ON_BEHALF_OF`, `AUTONOMOUS`                                                                                                                                                                                                                                                                                                        |
| `ConditionOp`         | `in`, `match`, `any`                                                                                                                                                                                                                                                                                                                |

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
| `NotAcceptableError`  | 406         |
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
  login    Authenticate and cache credentials locally.
  logout   Remove cached credentials.
  whoami   Show the currently cached tenant.
  agents   Agent inventory and lifecycle management.
  targets  MCP server target registry management.
  policies Access policy management.
  reports  Insights and activity map reporting.
```

### Global Options

Two ways to authenticate — pick whichever fits your workflow:

**Option A — one-time login (recommended for interactive/manual testing):**

```bash
# Service account OAuth2 client_credentials exchange (recommended — no raw JWT to paste):
secai-cli login \
  --tenant-url https://mytenant.aigw.cyberark.cloud \
  --identity-url https://mytenant.cyberark.cloud/api/idadmin \
  --client-id my-service-account \
  --client-secret ...

# Or, if you already have a bearer token from elsewhere, skip the OAuth exchange entirely:
secai-cli login --tenant-url https://mytenant.aigw.cyberark.cloud --token eyJhbGciOiJSUzI1NiJ9...
```

`login` validates the resulting credentials with a lightweight API call before caching them, so
a typo or bad client secret/token fails immediately instead of on your next command. Every
subsequent `secai-cli` command picks up the cached tenant URL/token automatically — no env vars
required.

**Option B — environment variables (recommended for CI/scripting):**

```bash
export SECAI_TENANT_URL=https://mytenant.cyberark.cloud
export SECAI_TOKEN=eyJhbGciOiJSUzI1NiJ9...
export SECAI_OUTPUT=json   # optional: table (default) | json | quiet
```

If both are present, env vars always win over a cached `login`, so scripted/CI usage is
unaffected by whatever is cached on a developer's machine.

---

### login / logout / whoami

```bash
secai-cli login [--tenant-url <url>] [--token <token>]
             [--identity-url <url>] [--client-id <id>] [--client-secret <secret>]
secai-cli logout
secai-cli whoami
```

| Option            | Required?                                  | Falls back to                          |
| ----------------- | ------------------------------------------ | -------------------------------------- |
| `--tenant-url`    | Always                                     | `$SECAI_TENANT_URL`, then prompt       |
| `--token`         | No — skips the OAuth2 exchange if supplied | —                                      |
| `--identity-url`  | Only if `--token` is omitted               | `$IDIRA_IDENTITY_URL`, then prompt     |
| `--client-id`     | Only if `--token` is omitted               | `$IDIRA_ADMIN_USER`, then prompt       |
| `--client-secret` | Only if `--token` is omitted               | `$IDIRA_ADMIN_PWD`, then hidden prompt |

- `login` — resolves a bearer token one of two ways. If `--token` is supplied, it's used
  directly. Otherwise, `login` exchanges a service account's `client_id`/`client_secret` for a
  token via OAuth2 `client_credentials` (`POST {identity_url}/oauth2/platformtoken`), so you
  never need to copy/paste a raw JWT. Either way, the resolved token is verified with a test API
  call, then cached via the OS keyring or a `0600` plaintext file — see
  [Credential Storage](#credential-storage) for how that's chosen, and `login`'s own output for
  which one was actually used. When the OAuth exchange was used, the
  `identity_url`/`client_id`/`client_secret` are cached alongside the token so the CLI can
  silently re-authenticate on a `401` without re-running `login` (see [Resilience](#resilience));
  logging in with `--token` opts out of this and only caches the token itself.
- `logout` — deletes the cached credentials from both the OS keyring and the plaintext file.
- `whoami` — prints the currently cached tenant URL, a masked token, the active storage backend,
  and whether auto-refresh on expiry is available for the current session (does not call the API).

---

### agents commands

#### `agents list`

```bash
secai-cli agents list [--page-size <n>] [--continuation-token <token>] [--output TABLE|JSON|QUIET]
```

List one page of agents (default page size is server-determined). The table view colour-codes
lifecycle states (green=ACTIVE, yellow=SUSPENDED, red=CONNECTION_ERROR). Pass the
`continuationToken` from a previous JSON response's `pageInfo` to fetch the next page.

```bash
secai-cli agents list --page-size 50
secai-cli agents list --output json | jq '.agents[].id'
```

---

#### `agents search`

```bash
secai-cli agents search <filter> [--page-size <n>] [--continuation-token <token>] [--output TABLE|JSON|QUIET]
```

Search agents by filter expression over `id`, `type`, `origin_id`, and `spiffeId`.

```bash
secai-cli agents search "type in [AWS_BEDROCK] and origin_id is null"
```

---

#### `agents summary`

```bash
secai-cli agents summary [--output TABLE|JSON|QUIET]
```

Show agent counts by type, by connection status, and SPIFFE/JWT counts.

---

#### `agents list-authn-descriptors <agent-id>`

```bash
secai-cli agents list-authn-descriptors <agent-id> [--output TABLE|JSON|QUIET]
```

---

#### `agents delete-authn-descriptor <agent-id> <descriptor-id>`

`--confirm` is required.

```bash
secai-cli agents delete-authn-descriptor a8f9c2d1 3f4e5d6c --confirm
```

---

#### `agents register`

```bash
secai-cli agents register \
  --name      <name>         Required. Alphanumeric, spaces, hyphens.
  --type      <type>         Required. Free-form (2-256 chars), e.g. CLAUDE, COPILOT, AWS_BEDROCK, CUSTOM.
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

Prints "No changes — request matched the stored agent." if the API returns `204 No Content`.

---

#### `agents set-state <agent-id> <state>`

State must be `ACTIVE` or `SUSPENDED`.

```bash
secai-cli agents set-state a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 SUSPENDED
secai-cli agents set-state a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 ACTIVE
```

---

#### `agents delete <agent-id>`

`--confirm` is required. The agent must be `SUSPENDED` or `PENDING_CONNECTION` first.

```bash
secai-cli agents set-state a8f9c2d1 SUSPENDED
secai-cli agents delete a8f9c2d1 --confirm
```

---

### targets commands

#### `targets list`

```bash
secai-cli targets list [--page-size <n>] [--next-cursor <cursor>] [--output TABLE|JSON|QUIET]
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
  --name <name>                     Required for CUSTOM; ignored for PREDEFINED (inherited from template).
  --description <text>
  --category <category>             Required for CUSTOM. See category list below.
  --url <upstream-url>              Required for CUSTOM.
  --auth-type OAUTH2.1|NONE|API_KEY|PAT   Optional for CUSTOM.
  --auth-server <url>               Optional. OAuth 2.1 authorization server.
  --jwks <url>                      Optional. JWKS endpoint for token validation.
  --client-id <id>                  Optional. OAuth 2.1 client ID.
  --client-secret <secret>          Optional. OAuth 2.1 client secret.
  --auth-header NAME=VALUE_TEMPLATE Repeatable. Upstream header (API_KEY/PAT).
  --api-key <key>                   Repeatable. Write-only API key value (API_KEY).
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

**Custom server with API_KEY auth:**

```bash
secai-cli targets register \
  --source CUSTOM \
  --name "My ServiceNow MCP" \
  --category ITSM_AND_INCIDENT_RESPONSE \
  --url https://servicenow-mcp.company.com/api \
  --auth-type API_KEY \
  --auth-header "Authorization=Bearer {{apiKey}}" \
  --api-key s3cr3t-key-value
```

**Predefined server from catalog:**

```bash
secai-cli targets register \
  --source PREDEFINED \
  --predefined-id 3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8
```

**Valid category values:**

| Value                                    | Description                    |
| ---------------------------------------- | ------------------------------ |
| `COMMUNICATION_AND_TEAM_CHAT`            | Slack, Teams, etc.             |
| `EMAIL_AND_SCHEDULING`                   | Outlook, Google Calendar, etc. |
| `KNOWLEDGE_BASES_AND_DOCS`               | Confluence, Notion, etc.       |
| `FILE_STORAGE_AND_CONTENT_REPOS`         | SharePoint, Google Drive, etc. |
| `DEVELOPER_TOOLS_AND_SOURCE_CONTROL`     | GitHub, GitLab, etc.           |
| `DATABASES_AND_DATA_STORES`              | Postgres, MongoDB, etc.        |
| `OBSERVABILITY_MONITORING_AND_TELEMETRY` | Datadog, Grafana, etc.         |
| `ITSM_AND_INCIDENT_RESPONSE`             | Jira, ServiceNow, etc.         |
| `WEB_AND_BROWSER_AUTOMATION`             | Web scraping, browser tools    |
| `CLOUD_AND_INFRASTRUCTURE_OPERATIONS`    | AWS, Azure, GCP, etc.          |

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
  [--auth-header NAME=VALUE_TEMPLATE ...]   # Rotate upstream headers (API_KEY/PAT targets only)
  [--api-key <key> ...]                     # Rotate API keys (API_KEY targets only)
  [--output TABLE|JSON|QUIET]
```

```bash
secai-cli targets edit tgt-custom-slack-001 \
  --description "Updated description" \
  --tag env=staging \
  --tag team=platform
```

```bash
# Rotate a stored API key
secai-cli targets edit tgt-custom-servicenow-001 --api-key new-secret-key
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

Returns the template plus its `tools` list.

```bash
secai-cli targets get-predefined 3f4e5d6c-7b8a-4c9d-a1e2-f3b4c5d6e7f8
```

---

### policies commands

#### `policies list`

```bash
secai-cli policies list [--page-size <n>] [--cursor <cursor>] [--output TABLE|JSON|QUIET]
```

---

#### `policies create`

```bash
secai-cli policies create \
  --name <name>                      Required.
  --access-type ON_BEHALF_OF|AUTONOMOUS   Required.
  --description <text>                Optional.
  --state ENABLED|DISABLED            Optional (default ENABLED).
  --agent-id <uuid>                   Repeatable. Omit for an "any agent" group.
  --user-role-id <role-id>            Repeatable. Required for ON_BEHALF_OF; forbidden for AUTONOMOUS.
  --resource-match <glob>             Repeatable, e.g. 'mcp:reporting:*'.
  --tag KEY=VALUE                     Repeatable.
  --owner-id <user-id>                Repeatable.
  --output TABLE|JSON|QUIET
```

```bash
secai-cli policies create \
  --name "Finance agent on-behalf-of policy" \
  --access-type ON_BEHALF_OF \
  --agent-id a8f9c2d1-3e4b-42fa-bb71-2a913d45ef12 \
  --user-role-id finance-role-id
```

---

#### `policies get <id>`

```bash
secai-cli policies get <policy-id>
```

---

#### `policies update <id>`

```bash
secai-cli policies update <policy-id> \
  [--name <name>] [--description <text>] [--state ENABLED|DISABLED]
  [--agent-id <uuid> ...] [--user-role-id <role-id> ...] [--resource-match <glob> ...]
  [--tag KEY=VALUE ...] [--owner-id <user-id> ...]
```

```bash
secai-cli policies update a8f9c2d1 --description "Updated description."
```

---

#### `policies delete <id>`

`--confirm` required. The policy must be `DISABLED` first.

```bash
secai-cli policies set-state <policy-id> DISABLED
secai-cli policies delete <policy-id> --confirm
```

---

#### `policies set-state <id> <state>`

State must be `ENABLED` or `DISABLED`.

```bash
secai-cli policies set-state <policy-id> DISABLED
secai-cli policies set-state <policy-id> ENABLED
```

---

### reports commands

#### `reports activity-map`

```bash
secai-cli reports activity-map [--format html|json] [--output TABLE|JSON|QUIET]
```

Prints the presigned `download_url` and the covered `date_range` for the tenant's activity-map
report.

```bash
secai-cli reports activity-map --format json --output json | jq -r '.downloadUrl'
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

Most of the test suite (`test_agents_cli.py`, `test_targets_cli.py`, `test_policies_cli.py`,
`test_reports_cli.py`) makes real API calls against a live tenant. `test_auth.py`,
`test_client_resilience.py`, and `test_pagination.py` are the exceptions — they cover the local
credential cache, `secai-cli login`/`logout`/`whoami`, the HTTP client's retry/backoff/
auto-refresh behavior, and the `iter_all*` pagination helpers using `pytest-httpx` mocks, so they
run fully offline with no tenant credentials required.

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push to `main` and
every pull request, across Python 3.10–3.13:

- `ruff check` (scoped to the `F`/`I`/`E501` rules, with a few pre-existing CLI files excluded —
  see the workflow's comments) and the offline pytest suite above are **blocking**.
- `mypy` runs across the whole `secai` package but is currently **informational only**
  (`continue-on-error`) — the project's `strict = true` mypy config surfaces some pre-existing
  type errors unrelated to any single change, so it reports without blocking merges until that
  debt is cleaned up.
- The full live-tenant suite isn't run in CI since it needs real credentials; run it locally as
  described below before releasing.

Configure credentials first (only needed for the live tests):

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

# Policies only
pytest tests/test_policies_cli.py -v

# Reports only
pytest tests/test_reports_cli.py -v

# Auth/login — offline, no tenant credentials needed
pytest tests/test_auth.py -v

# HTTP client retry/backoff/auto-refresh — offline, no tenant credentials needed
pytest tests/test_client_resilience.py -v

# Pagination helpers (iter_all) — offline, no tenant credentials needed
pytest tests/test_pagination.py -v

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
- `test_auth.py` isolates the credential cache per-test via a `tmp_path`-based fixture and
  mocks both the OAuth2 token endpoint and the login validation call, so it never touches the
  real filesystem location (`~/.config/secai`) or network. An autouse fixture also stubs
  `_import_keyring()` to report "unavailable" by default so tests never read/write the _real_
  OS keychain. Its `TestKeyringBackend` class explicitly re-patches that stub with a fake
  `keyring` module to exercise the OS-keyring storage backend (available/working,
  installed-but-unusable, opportunistic file→keyring migration, `SECAI_NO_KEYRING`) fully
  offline, regardless of what keyring backend (if any) happens to be usable on the machine
  running the tests.
- `test_client_resilience.py` drives `_BaseClient` directly with `pytest-httpx` to assert the
  retry/backoff and 401 auto-refresh behavior (exhaustion, `Retry-After` handling, GET-only
  retry of plain `500`s, successful/failed reauth) without any real HTTP traffic.
- `test_pagination.py` mocks each resource's list endpoint with `pytest-httpx` to verify the
  `iter_all()`/`iter_all_mcp_servers()` generators follow `continuation_token`/`next_cursor`
  across multiple pages and stop on an empty or token-less page (including a defensive case
  where a buggy server returns an empty page alongside a non-null cursor).

---

## Quickstart Example

The file `sdk-quickstart/quickstart.py` demonstrates the complete workflow end-to-end.

```bash
export SECAI_TENANT_URL=https://mytenant.cyberark.cloud
export SECAI_TOKEN=$(cat my_jwt.txt)

python sdk-quickstart/quickstart.py
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

── Editing agent ────────────────────────────────────────────────
  Description: Updated by the SDK quickstart.
  Tags       : {'source': 'quickstart'}

── Registering MCP server ───────────────────────────────────────
  Registered : tgt-sdk-...
  State      : ENABLED
  Gateway    : https://aigw.cyberark.cloud/mcp/sdk

── Editing MCP server ───────────────────────────────────────────
  Description: Updated by the SDK quickstart.

── Predefined MCP catalog ───────────────────────────────────────
  3f4e5d6c  Slack MCP Server               COMMUNICATION_AND_TEAM_CHAT
  5a6b7c8d  GitHub MCP Server              DEVELOPER_TOOLS_AND_SOURCE_CONTROL

── Creating access policy ───────────────────────────────────────
  Created   : 7c6b5a4d-...
  Name      : SDK Quickstart Policy
  AccessType: AUTONOMOUS

── Activity map report ───────────────────────────────────────────
  Download URL: https://.../activity-map.html?X-Amz-...
  Date range  : 2024-01-01 to 2024-01-31

── Cleanup ──────────────────────────────────────────────────────
  Policy deleted  : 7c6b5a4d-...
  Agent suspended : f1e2d3c4-...
  Agent deleted   : f1e2d3c4-...
  MCP disabled   : tgt-sdk-...
  MCP deleted    : tgt-sdk-...

Done.
```

---

## Project Layout

```plaintext
idira-secai-sdk/
├── .github/workflows/ci.yml    # CI: ruff + offline pytest (blocking), mypy (informational)
├── CHANGELOG.md                # Version history, including breaking changes
├── pyproject.toml              # Package metadata and dependencies
├── scratch/                    # API spec + diff/usage notes (not part of the package)
│
├── secai/                      # SDK library
│   ├── __init__.py             # Public API surface
│   ├── client.py               # SecAIClient and _BaseClient
│   ├── agents.py               # AgentsResource (9 methods)
│   ├── targets.py              # TargetsResource (8 methods)
│   ├── policies.py             # PoliciesResource (6 methods)
│   ├── reports.py              # ReportsResource (1 method)
│   ├── models.py               # Pydantic v2 request/response models
│   ├── exceptions.py           # SecAIError hierarchy
│   └── cli/
│       ├── __init__.py
│       ├── main.py             # Typer app + sub-group registration
│       ├── auth.py             # Local credential cache + OAuth exchange + token refresher
│       ├── auth_cmds.py        # login/logout/whoami top-level commands
│       ├── agents_cmds.py      # agents list/search/summary/register/get/edit/delete/
│       │                       #        set-state/list-authn-descriptors/delete-authn-descriptor
│       ├── targets_cmds.py     # targets list/register/get/edit/delete/set-state/
│       │                       #        list-predefined/get-predefined
│       ├── policies_cmds.py    # policies list/create/get/update/delete/set-state
│       └── reports_cmds.py     # reports activity-map
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Session fixtures (live agent + MCP server)
│   ├── test_agents_cli.py      # Agent test cases (positive + negative)
│   ├── test_targets_cli.py     # Target test cases (positive + negative)
│   ├── test_policies_cli.py    # Policy test cases (positive + negative)
│   ├── test_reports_cli.py     # Report test cases (positive + negative)
│   ├── test_auth.py            # login/logout/whoami + credential cache (offline, mocked)
│   ├── test_client_resilience.py  # Retry/backoff + 401 auto-refresh (offline, mocked)
│   └── test_pagination.py      # iter_all()/iter_all_mcp_servers() helpers (offline, mocked)
│
└── sdk-quickstart/
    └── quickstart.py           # Annotated end-to-end walkthrough
```

---

## API Endpoint Coverage

| Method | Endpoint                                      | SDK method                                          | CLI command                                              |
| ------ | --------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------- |
| GET    | `/api/agents`                                 | `client.agents.list()`                              | `secai-cli agents list`                                  |
| POST   | `/api/agents/search`                          | `client.agents.search(req)`                         | `secai-cli agents search <filter>`                       |
| GET    | `/api/agents/summary`                         | `client.agents.summary()`                           | `secai-cli agents summary`                               |
| POST   | `/api/agents`                                 | `client.agents.register(req)`                       | `secai-cli agents register`                              |
| GET    | `/api/agents/{id}`                            | `client.agents.get(id)`                             | `secai-cli agents get <id>`                              |
| PUT    | `/api/agents/{id}`                            | `client.agents.edit(id, req)`                       | `secai-cli agents edit <id>`                             |
| DELETE | `/api/agents/{id}`                            | `client.agents.delete(id)`                          | `secai-cli agents delete <id> --confirm`                 |
| POST   | `/api/agents/{id}/state`                      | `client.agents.set_state(id, state)`                | `secai-cli agents set-state <id> <state>`                |
| GET    | `/api/agents/{id}/authn-descriptors`          | `client.agents.list_authn_descriptors(id)`          | `secai-cli agents list-authn-descriptors <id>`           |
| DELETE | `/api/agents/{id}/authn-descriptors/{descId}` | `client.agents.delete_authn_descriptor(id, descId)` | `secai-cli agents delete-authn-descriptor <id> <descId>` |
| GET    | `/api/targets/mcp-servers`                    | `client.targets.list_mcp_servers()`                 | `secai-cli targets list`                                 |
| POST   | `/api/targets/mcp-servers`                    | `client.targets.register_mcp_server(req)`           | `secai-cli targets register`                             |
| GET    | `/api/targets/mcp-servers/{id}`               | `client.targets.get_mcp_server(id)`                 | `secai-cli targets get <id>`                             |
| PUT    | `/api/targets/mcp-servers/{id}`               | `client.targets.edit_mcp_server(id, req)`           | `secai-cli targets edit <id>`                            |
| DELETE | `/api/targets/mcp-servers/{id}`               | `client.targets.delete_mcp_server(id)`              | `secai-cli targets delete <id> --confirm`                |
| POST   | `/api/targets/mcp-servers/{id}/state`         | `client.targets.set_mcp_server_state(id, state)`    | `secai-cli targets set-state <id> <state>`               |
| GET    | `/api/targets/predefined/mcp-servers`         | `client.targets.list_predefined_mcp_servers()`      | `secai-cli targets list-predefined`                      |
| GET    | `/api/targets/predefined/mcp-servers/{id}`    | `client.targets.get_predefined_mcp_server(id)`      | `secai-cli targets get-predefined <id>`                  |
| GET    | `/api/policies`                               | `client.policies.list()`                            | `secai-cli policies list`                                |
| POST   | `/api/policies`                               | `client.policies.create(req)`                       | `secai-cli policies create`                              |
| GET    | `/api/policies/{id}`                          | `client.policies.get(id)`                           | `secai-cli policies get <id>`                            |
| PUT    | `/api/policies/{id}`                          | `client.policies.update(id, req)`                   | `secai-cli policies update <id>`                         |
| DELETE | `/api/policies/{id}`                          | `client.policies.delete(id)`                        | `secai-cli policies delete <id> --confirm`               |
| POST   | `/api/policies/{id}/state`                    | `client.policies.set_state(id, state)`              | `secai-cli policies set-state <id> <state>`              |
| GET    | `/api/files/activity-map`                     | `client.reports.get_activity_map()`                 | `secai-cli reports activity-map`                         |

---

## License

Apache 2.0 — see [LICENSE](http://www.apache.org/licenses/LICENSE-2.0.html).
