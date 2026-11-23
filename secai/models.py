"""Pydantic v2 request/response models for the SecAI API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Union

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentType(str, Enum):
    COPILOT = "COPILOT"
    CLAUDE = "CLAUDE"
    CUSTOM = "CUSTOM"


class AgentState(str, Enum):
    PENDING_CONNECTION = "PENDING_CONNECTION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CONNECTION_ERROR = "CONNECTION_ERROR"


class OwnerType(str, Enum):
    USER = "USER"
    ROLE = "ROLE"


class McpSourceType(str, Enum):
    CUSTOM = "CUSTOM"
    PREDEFINED = "PREDEFINED"


class McpAuthType(str, Enum):
    OAUTH2_1 = "OAUTH2.1"
    NONE = "NONE"
    API_KEY = "API_KEY"
    PAT = "PAT"


class OauthApplicationRegistration(str, Enum):
    DYNAMIC = "dynamic"
    MANUAL = "manual"


class AuthnDescriptorType(str, Enum):
    JWT = "jwt"
    JWT_SVID = "jwt-svid"
    OAUTH2 = "oauth2"


class PolicyState(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class PolicyAccessType(str, Enum):
    ON_BEHALF_OF = "ON_BEHALF_OF"
    AUTONOMOUS = "AUTONOMOUS"


class McpCategory(str, Enum):
    COMMUNICATION_AND_TEAM_CHAT = "COMMUNICATION_AND_TEAM_CHAT"
    EMAIL_AND_SCHEDULING = "EMAIL_AND_SCHEDULING"
    KNOWLEDGE_BASES_AND_DOCS = "KNOWLEDGE_BASES_AND_DOCS"
    FILE_STORAGE_AND_CONTENT_REPOS = "FILE_STORAGE_AND_CONTENT_REPOS"
    DEVELOPER_TOOLS_AND_SOURCE_CONTROL = "DEVELOPER_TOOLS_AND_SOURCE_CONTROL"
    DATABASES_AND_DATA_STORES = "DATABASES_AND_DATA_STORES"
    OBSERVABILITY_MONITORING_AND_TELEMETRY = "OBSERVABILITY_MONITORING_AND_TELEMETRY"
    ITSM_AND_INCIDENT_RESPONSE = "ITSM_AND_INCIDENT_RESPONSE"
    WEB_AND_BROWSER_AUTOMATION = "WEB_AND_BROWSER_AUTOMATION"
    CLOUD_AND_INFRASTRUCTURE_OPERATIONS = "CLOUD_AND_INFRASTRUCTURE_OPERATIONS"


class McpState(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class Owner(BaseModel):
    id: str
    name: str
    type: OwnerType = OwnerType.USER
    source_directory_name: str | None = Field(default=None, alias="sourceDirectoryName")
    source_directory_id: str | None = Field(default=None, alias="sourceDirectoryId")

    model_config = {"populate_by_name": True}


class AgentStatus(BaseModel):
    state: AgentState
    message: str | None = None


# ---------------------------------------------------------------------------
# Authentication descriptor models (SPIFFE / JWT / OAuth2 agent auth)
# ---------------------------------------------------------------------------


class AuthnDescriptorInput(BaseModel):
    """An authentication descriptor sent on register/edit agent requests."""

    type: AuthnDescriptorType
    sub_type: str | None = Field(default=None, alias="subType")
    id: str | None = None
    service_id: str | None = Field(default=None, alias="serviceId")
    client_id: str | None = Field(default=None, alias="clientId")
    data: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class AuthnDescriptorEntry(BaseModel):
    """An authentication descriptor as nested on an ``Agent`` response."""

    type: str | None = None
    sub_type: str | None = Field(default=None, alias="subType")
    id: str | None = None
    service_id: str | None = Field(default=None, alias="serviceId")
    data: dict[str, Any] | None = None
    client_id: str | None = Field(default=None, alias="clientId")
    client_secret: str | None = Field(default=None, alias="clientSecret")

    model_config = {"populate_by_name": True}


class AuthnDescriptorOutput(BaseModel):
    """An authentication descriptor as returned by the authn-descriptors endpoints."""

    id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Agent models
# ---------------------------------------------------------------------------


class RegisterAgentRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=256, pattern=r"^[A-Za-z0-9 _-]+$")
    type: str = Field(..., min_length=2, max_length=256)
    redirect_callback_urls: list[str] = Field(
        default_factory=list,
        alias="redirectCallbackUrls",
        max_length=10,
    )
    description: str | None = Field(None, max_length=500)
    owner: str | None = Field(None, min_length=2)
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict, max_length=10)
    agent_subtype: str | None = Field(default=None, alias="agentSubtype")
    origin_id: str | None = Field(default=None, alias="originId")
    authn_descriptors: list[AuthnDescriptorInput] = Field(
        default_factory=list, alias="authnDescriptors"
    )

    model_config = {"populate_by_name": True}

    @field_validator("redirect_callback_urls", mode="before")
    @classmethod
    def _validate_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            if not url.startswith("https://"):
                raise ValueError(f"Callback URL must start with https://: {url}")
        return v


class EditAgentRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=256, pattern=r"^[A-Za-z0-9 _-]+$")
    type: str | None = None
    description: str | None = Field(None, max_length=500)
    owner: str | None = Field(None, min_length=2)
    owners: list[Owner] | None = None
    redirect_callback_urls: list[str] | None = Field(default=None, alias="redirectCallbackUrls")
    tags: dict[str, str] | None = None
    origin_id: str | None = Field(default=None, alias="originId")
    authn_descriptors: list[AuthnDescriptorInput] | None = Field(
        default=None, alias="authnDescriptors"
    )

    model_config = {"populate_by_name": True}


class AgentCredentials(BaseModel):
    client_id: str | None = Field(default=None, alias="clientId")
    client_secret: str | None = Field(default=None, alias="clientSecret")
    gateway_url: str | None = Field(default=None, alias="gatewayUrl")

    model_config = {"populate_by_name": True}


class Agent(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    description: str | None = None
    owner: str | None = None
    owners: list[Owner] = Field(default_factory=list)
    redirect_callback_urls: list[str] = Field(default_factory=list, alias="redirectCallbackUrls")
    tags: dict[str, str] = Field(default_factory=dict)
    client_id: str | None = Field(default=None, alias="clientId")
    status: AgentStatus | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    updated_by: str | None = Field(default=None, alias="updatedBy")
    agent_subtype: str | None = Field(default=None, alias="agentSubtype")
    origin_id: str | None = Field(default=None, alias="originId")
    last_used: datetime | None = Field(default=None, alias="lastUsed")
    authn_descriptors: list[AuthnDescriptorEntry] = Field(
        default_factory=list, alias="authnDescriptors"
    )

    model_config = {"populate_by_name": True}

    @field_validator("owners", "redirect_callback_urls", "authn_descriptors", mode="before")
    @classmethod
    def _coerce_list_none(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return {} if v is None else v


class AgentWithCredentials(Agent):
    credentials: AgentCredentials | None = None


class AgentStateRequest(BaseModel):
    state: AgentState


class AgentStateResponse(BaseModel):
    id: str | None = None
    status: AgentStatus | None = None


class PageInfo(BaseModel):
    """Cursor-based pagination details returned alongside a list of agents."""

    page_size: int | None = Field(default=None, alias="pageSize")
    continuation_token: str | None = Field(default=None, alias="continuationToken")

    model_config = {"populate_by_name": True}


class ListAgentsResponse(BaseModel):
    agents: list[Agent] = Field(default_factory=list)
    page_info: PageInfo | None = Field(default=None, alias="pageInfo")
    total_count: int | None = Field(default=None, alias="totalCount")

    model_config = {"populate_by_name": True}


class SearchAgentsRequest(BaseModel):
    """Request body for ``POST /agents/search``."""

    filter: str
    page_size: int | None = Field(default=None, alias="pageSize", ge=1, le=1000)
    continuation_token: str | None = Field(default=None, alias="continuationToken")

    model_config = {"populate_by_name": True}


class SummaryItem(BaseModel):
    key: str | None = None
    display_text: str | None = Field(default=None, alias="displayText")
    total: int | None = None

    model_config = {"populate_by_name": True}


class SummaryData(BaseModel):
    total: int | None = None
    items: list[SummaryItem] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AgentsSummary(BaseModel):
    """Response body for ``GET /agents/summary``."""

    types: SummaryData | None = None
    statuses: SummaryData | None = None
    spiffe_count: int = Field(0, alias="spiffeCount")
    jwt_count: int = Field(0, alias="jwtCount")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# MCP server / target models
# ---------------------------------------------------------------------------


class McpSource(BaseModel):
    type: McpSourceType
    predefined_target_id: str | None = Field(default=None, alias="predefinedTargetId")
    predefined_target_version: int | None = Field(default=None, alias="predefinedTargetVersion")

    model_config = {"populate_by_name": True}


class McpUpstream(BaseModel):
    url: str


class UpstreamHeader(BaseModel):
    """A header forwarded to the upstream MCP server for API_KEY/PAT auth."""

    name: str
    value_template: str = Field(..., alias="valueTemplate")

    model_config = {"populate_by_name": True}


class ApiKeyEntry(BaseModel):
    """A write-only API key supplied on register/edit requests."""

    api_key: str = Field(..., alias="apiKey")

    model_config = {"populate_by_name": True}


class ApiKeyMetadata(BaseModel):
    """Metadata about a stored API key, as returned on ``McpServerResponse``."""

    created_at: datetime | None = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class McpAuthMethod(BaseModel):
    """Authentication configuration for a custom or predefined MCP server.

    Mirrors the API's ``oneOf`` of ``OAUTH2.1`` / ``NONE`` / ``API_KEY`` /
    ``PAT`` auth methods with one flexible model rather than four separate
    classes, since only a subset of fields applies to any given ``type``.
    Fields irrelevant to a given ``type`` are simply left unset.
    """

    type: McpAuthType
    authorization_server: str | None = Field(default=None, alias="authorizationServer")
    jwks: str | None = Field(default=None, alias="JWKS")
    # OAUTH2.1 only. client_secret and api_keys[].api_key are write-only and
    # never returned by the server.
    client_id: str | None = Field(default=None, alias="clientId")
    client_secret: str | None = Field(default=None, alias="clientSecret")
    registration_endpoint: str | None = Field(default=None, alias="registrationEndpoint")
    # API_KEY / PAT only.
    headers: list[UpstreamHeader] = Field(default_factory=list)
    api_keys: list[ApiKeyEntry] = Field(default_factory=list, alias="apiKeys")
    # API_KEY response only (replaces api_keys[].api_key, which is write-only).
    api_key_metadata: list[ApiKeyMetadata] = Field(default_factory=list, alias="apiKeyMetadata")

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _coerce_response_api_keys(cls, data: Any) -> Any:
        """Route response-shaped ``apiKeys`` (``{createdAt}``) to ``apiKeyMetadata``.

        Request payloads send ``apiKeys: [{"apiKey": "..."}]`` (write-only);
        responses for API_KEY targets return ``apiKeys: [{"createdAt": "..."}]``
        instead. Both use the ``apiKeys`` wire key, so disambiguate on parse.
        """
        if isinstance(data, dict) and isinstance(data.get("apiKeys"), list):
            entries = data["apiKeys"]
            if entries and all(isinstance(e, dict) and "apiKey" not in e for e in entries):
                data = {**data, "apiKeyMetadata": entries, "apiKeys": []}
        return data


class AuthMethodUpdate(BaseModel):
    """Request body for updating an API_KEY/PAT target's credentials.

    Used only via ``EditMcpServerRequest.auth_method`` — OAuth/NONE targets
    cannot change their ``authMethod`` after registration.
    """

    type: McpAuthType | None = None
    headers: list[UpstreamHeader] | None = None
    api_keys: list[ApiKeyEntry] | None = Field(default=None, alias="apiKeys")

    model_config = {"populate_by_name": True}


class McpServerResponse(BaseModel):
    id: str | None = None
    source: McpSource | None = None
    name: str | None = None
    description: str | None = None
    category: McpCategory | None = None
    gateway_url: str | None = Field(default=None, alias="gatewayUrl")
    # OAuth redirect URI for targets using an Idira-managed OAuth app; null
    # for passthrough OAuth, API_KEY, PAT, and NONE targets.
    callback_url: str | None = Field(default=None, alias="callbackUrl")
    upstream: McpUpstream | None = None
    auth_method: McpAuthMethod | None = Field(default=None, alias="authMethod")
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    state: McpState | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}

    @field_validator("owners", mode="before")
    @classmethod
    def _coerce_list_none(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return {} if v is None else v


class RegisterCustomMcpServerRequest(BaseModel):
    """Request body for ``POST /targets/mcp-servers`` with ``source.type=CUSTOM``.

    Matches the API's ``CustomMcpServerData`` schema exactly (including its
    ``additionalProperties: false`` constraint) — ``name``, ``description``,
    ``category``, and ``upstream`` are all required.
    """

    source: McpSource = Field(default_factory=lambda: McpSource(type=McpSourceType.CUSTOM))
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., max_length=500)
    category: McpCategory
    upstream: McpUpstream
    auth_method: McpAuthMethod | None = Field(default=None, alias="authMethod")
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("source")
    @classmethod
    def _force_custom_source(cls, v: McpSource) -> McpSource:
        if v.type != McpSourceType.CUSTOM:
            raise ValueError("source.type must be CUSTOM for RegisterCustomMcpServerRequest")
        return v


class RegisterPredefinedMcpServerRequest(BaseModel):
    """Request body for ``POST /targets/mcp-servers`` with ``source.type=PREDEFINED``.

    Matches the API's ``PredefinedMcpServerData`` schema — only ``source``
    (with ``predefinedTargetId``) is required. ``category`` and ``upstream``
    are not accepted here; they are always inherited from the template.
    """

    source: McpSource
    description: str | None = Field(None, max_length=500)
    auth_method: McpAuthMethod | None = Field(default=None, alias="authMethod")
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("source")
    @classmethod
    def _require_predefined_id(cls, v: McpSource) -> McpSource:
        if v.type != McpSourceType.PREDEFINED:
            raise ValueError(
                "source.type must be PREDEFINED for RegisterPredefinedMcpServerRequest"
            )
        if not v.predefined_target_id:
            raise ValueError("source.predefinedTargetId is required for PREDEFINED MCP servers")
        return v


# Accepted by ``TargetsResource.register_mcp_server`` — the caller picks the
# branch that matches their ``source.type``.
RegisterMcpServerRequest = Union[RegisterCustomMcpServerRequest, RegisterPredefinedMcpServerRequest]


class EditMcpServerRequest(BaseModel):
    """Request body for PUT /api/targets/mcp-servers/{Id}.

    Allowed: description, category, owners, tags, and (API_KEY/PAT targets
    only) auth_method credential rotation.
    """

    description: str | None = None
    category: McpCategory | None = None
    owners: list[Owner] | None = None
    tags: dict[str, str] | None = None
    auth_method: AuthMethodUpdate | None = Field(default=None, alias="authMethod")

    model_config = {"populate_by_name": True}


class McpServerStateRequest(BaseModel):
    state: McpState


class McpServerListResponse(BaseModel):
    mcp_servers: list[McpServerResponse] = Field(default_factory=list, alias="mcpServers")
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = {"populate_by_name": True}


class PredefinedMcpTool(BaseModel):
    """A tool advertised by a predefined MCP server template."""

    name: str
    description: str


class PredefinedMcpTarget(BaseModel):
    id: str | None = None
    # The predefined catalog returns "version" while registered-target payloads
    # use "predefinedTargetVersion".  Accept both so the same model works for
    # both response shapes.
    predefined_target_version: int | None = Field(
        None,
        validation_alias=AliasChoices("predefinedTargetVersion", "version"),
        serialization_alias="predefinedTargetVersion",
    )
    name: str | None = None
    icon_id: str | None = Field(default=None, alias="iconId")
    description: str | None = None
    category: McpCategory | None = None
    upstream: McpUpstream | None = None
    # Predefined catalog returns authMethod as a plain string ("NONE",
    # "OAUTH2.1"); registered-target payloads return it as an object
    # {"type": "NONE"}.  Coerce the string form to the object form.
    auth_method: McpAuthMethod | None = Field(default=None, alias="authMethod")
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = Field(default=None, alias="createdAt")
    # Per-tenant OAuth callback URL; present only for OAuth 2.1 templates
    # routed through the gateway.
    callback_url: str | None = Field(default=None, alias="callbackUrl")
    # How OAuth client registration is performed for this template ("dynamic"
    # or "manual"); present only for OAuth 2.1 templates.
    oauth_application_registration: OauthApplicationRegistration | None = Field(
        None, alias="oauthApplicationRegistration"
    )
    # RFC 7591 dynamic-client-registration endpoint; present only for
    # "dynamic" OAuth 2.1 templates.
    registration_endpoint: str | None = Field(default=None, alias="registrationEndpoint")

    model_config = {"populate_by_name": True}

    @field_validator("auth_method", mode="before")
    @classmethod
    def _coerce_auth_method(cls, v: Any) -> Any:
        """Accept a bare auth-type string and wrap it in the expected dict."""
        if isinstance(v, str):
            return {"type": v}
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags_none(cls, v: Any) -> Any:
        return {} if v is None else v


class PredefinedMcpTargetDetail(PredefinedMcpTarget):
    """Response body for ``GET /targets/predefined/mcp-servers/{Id}``.

    Extends the catalog list-item schema with the tools the template exposes.
    """

    tools: list[PredefinedMcpTool] = Field(default_factory=list)


class PredefinedMcpListResponse(BaseModel):
    targets: list[PredefinedMcpTarget] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error model (for parsing API error bodies)
# ---------------------------------------------------------------------------


class ApiError(BaseModel):
    code: str | None = None
    message: str | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Policy models
# ---------------------------------------------------------------------------
#
# The API models each match group's single condition as a strict
# discriminated ``oneOf`` (e.g. ``AgentInCondition`` | ``AnyCondition``),
# differing per group kind (agent/user/resource) in which ``op``/``key``
# values are legal. Rather than reproducing four near-identical condition
# classes, a single flexible ``Condition`` model is used everywhere (matching
# the SDK's existing pattern of favoring ergonomics over strict typing), with
# field validation limited to what is universally true: ``op`` must be one of
# "in" | "match" | "any".


class ConditionOp(str, Enum):
    IN = "in"
    MATCH = "match"
    ANY = "any"


class Condition(BaseModel):
    """A single match condition within a policy's agent/user/resource group.

    Legal ``key``/``value`` combinations depend on both the group kind and
    ``op`` (see the API reference), e.g. ``{"op": "in", "key": "id", "value":
    [...]}`` or ``{"op": "any"}``. These are enforced server-side.
    """

    op: ConditionOp
    key: str | None = None
    value: list[str] | str | None = None

    model_config = {"populate_by_name": True}


class ConditionGroup(BaseModel):
    """A single-condition match group; groups are OR-combined by their parent array."""

    conditions: list[Condition] = Field(..., min_length=1, max_length=1)


class PolicyInput(BaseModel):
    """Request body for ``POST /policies``.

    ``access_type`` determines whether ``user`` is required
    (``ON_BEHALF_OF``) or forbidden (``AUTONOMOUS``); enforced client-side to
    fail fast, mirroring the ``RegisterMcpServerRequest`` validation pattern.
    """

    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=500)
    tags: dict[str, Any] = Field(default_factory=dict)
    state: PolicyState
    owners: list[Owner] = Field(default_factory=list)
    access_type: PolicyAccessType = Field(..., alias="accessType")
    agent: list[ConditionGroup] = Field(..., min_length=1)
    user: list[ConditionGroup] | None = None
    resources: list[ConditionGroup] = Field(..., min_length=1)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_user_grant(self) -> PolicyInput:
        if self.access_type == PolicyAccessType.ON_BEHALF_OF:
            if not self.user:
                raise ValueError("user is required when accessType is ON_BEHALF_OF")
        elif self.user is not None:
            raise ValueError("user must not be set when accessType is AUTONOMOUS")
        return self


class PolicyUpdate(BaseModel):
    """Request body for ``PUT /policies/{id}``. All fields are optional.

    ``accessType`` is fixed at creation and cannot be changed; the server
    rejects a ``user`` grant that becomes inconsistent with the stored
    ``accessType`` (required for ``ON_BEHALF_OF``, forbidden for
    ``AUTONOMOUS``) — this isn't re-validated client-side since the current
    ``accessType`` isn't part of the update payload.
    """

    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = Field(None, max_length=500)
    tags: dict[str, Any] | None = None
    state: PolicyState | None = None
    owners: list[Owner] | None = None
    agent: list[ConditionGroup] | None = None
    user: list[ConditionGroup] | None = None
    resources: list[ConditionGroup] | None = None

    model_config = {"populate_by_name": True}


class PolicyOutput(BaseModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    owners: list[Owner] = Field(default_factory=list)
    state: PolicyState | None = None
    access_type: PolicyAccessType | None = Field(default=None, alias="accessType")
    agent: list[ConditionGroup] = Field(default_factory=list)
    user: list[ConditionGroup] | None = None
    resources: list[ConditionGroup] = Field(default_factory=list)
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}

    @field_validator("owners", "agent", "resources", mode="before")
    @classmethod
    def _coerce_list_none(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return {} if v is None else v


class ListPolicyOutput(BaseModel):
    policies: list[PolicyOutput] = Field(default_factory=list)
    next_cursor: str | None = Field(default=None, alias="nextCursor")

    model_config = {"populate_by_name": True}


class PolicyStateRequest(BaseModel):
    state: PolicyState


class PolicyStateResponse(BaseModel):
    id: str | None = None
    state: PolicyState | None = None


# ---------------------------------------------------------------------------
# Reports / activity map models
# ---------------------------------------------------------------------------


class ActivityMapDateRange(BaseModel):
    start: str | None = None
    end: str | None = None


class ActivityMapReport(BaseModel):
    """Response body for ``GET /files/activity-map``.

    ``download_url`` is a short-lived presigned S3 URL; the caller must issue
    a follow-up GET to it to retrieve the actual report file.
    """

    download_url: str | None = Field(default=None, alias="downloadUrl")
    date_range: ActivityMapDateRange | None = Field(default=None, alias="dateRange")

    model_config = {"populate_by_name": True}
