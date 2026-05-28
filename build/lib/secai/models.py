"""Pydantic v2 request/response models for the SecAI API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AgentType(str, Enum):
    COPILOT = "COPILOT"
    CLAUDE = "CLAUDE"
    CUSTOM = "CUSTOM"


class AgentState(str, Enum):
    PENDING_CONNECTION = "PENDING_CONNECTION"
    PENDING_CONFIGURATION = "PENDING_CONFIGURATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    ERROR = "ERROR"


class OwnerType(str, Enum):
    USER = "USER"
    ROLE = "ROLE"


class McpSourceType(str, Enum):
    CUSTOM = "CUSTOM"
    PREDEFINED = "PREDEFINED"


class McpAuthType(str, Enum):
    OAUTH2_1 = "OAUTH2.1"
    NONE = "NONE"


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
    source_directory_name: Optional[str] = Field(None, alias="sourceDirectoryName")
    source_directory_id: Optional[str] = Field(None, alias="sourceDirectoryId")

    model_config = {"populate_by_name": True}


class AgentStatus(BaseModel):
    state: AgentState
    message: Optional[str] = None


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
    description: Optional[str] = Field(None, max_length=500)
    owner: Optional[str] = Field(None, min_length=2)
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict, max_length=10)

    model_config = {"populate_by_name": True}

    @field_validator("redirect_callback_urls", mode="before")
    @classmethod
    def _validate_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            if not url.startswith("https://"):
                raise ValueError(f"Callback URL must start with https://: {url}")
        return v


class EditAgentRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=256, pattern=r"^[A-Za-z0-9 _-]+$")
    type: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    owner: Optional[str] = Field(None, min_length=2)
    owners: Optional[list[Owner]] = None
    redirect_callback_urls: Optional[list[str]] = Field(None, alias="redirectCallbackUrls")
    tags: Optional[dict[str, str]] = None

    model_config = {"populate_by_name": True}


class AgentCredentials(BaseModel):
    client_id: Optional[str] = Field(None, alias="clientId")
    client_secret: Optional[str] = Field(None, alias="clientSecret")
    gateway_url: Optional[str] = Field(None, alias="gatewayUrl")

    model_config = {"populate_by_name": True}


class Agent(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    owners: list[Owner] = Field(default_factory=list)
    redirect_callback_urls: list[str] = Field(default_factory=list, alias="redirectCallbackUrls")
    tags: dict[str, str] = Field(default_factory=dict)
    client_id: Optional[str] = Field(None, alias="clientId")
    status: Optional[AgentStatus] = None
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    created_by: Optional[str] = Field(None, alias="createdBy")
    updated_by: Optional[str] = Field(None, alias="updatedBy")

    model_config = {"populate_by_name": True}

    @field_validator("owners", "redirect_callback_urls", mode="before")
    @classmethod
    def _coerce_list_none(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return {} if v is None else v


class AgentWithCredentials(Agent):
    credentials: Optional[AgentCredentials] = None


class AgentStateRequest(BaseModel):
    state: AgentState


class AgentStateResponse(BaseModel):
    id: Optional[str] = None
    status: Optional[AgentStatus] = None


class ListAgentsResponse(BaseModel):
    agents: list[Agent] = Field(default_factory=list)
    count: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


# ---------------------------------------------------------------------------
# MCP server / target models
# ---------------------------------------------------------------------------


class McpSource(BaseModel):
    type: McpSourceType
    predefined_target_id: Optional[str] = Field(None, alias="predefinedTargetId")
    predefined_target_version: Optional[int] = Field(None, alias="predefinedTargetVersion")

    model_config = {"populate_by_name": True}


class McpUpstream(BaseModel):
    url: str


class McpAuthMethod(BaseModel):
    type: McpAuthType
    authorization_server: Optional[str] = Field(None, alias="authorizationServer")
    jwks: Optional[str] = Field(None, alias="JWKS")

    model_config = {"populate_by_name": True}


class McpServerResponse(BaseModel):
    id: Optional[str] = None
    source: Optional[McpSource] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[McpCategory] = None
    gateway_url: Optional[str] = Field(None, alias="gatewayUrl")
    upstream: Optional[McpUpstream] = None
    auth_method: Optional[McpAuthMethod] = Field(None, alias="authMethod")
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)
    state: Optional[McpState] = None
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    created_by: Optional[str] = Field(None, alias="createdBy")
    updated_by: Optional[str] = Field(None, alias="updatedBy")

    model_config = {"populate_by_name": True}

    @field_validator("owners", mode="before")
    @classmethod
    def _coerce_list_none(cls, v: Any) -> Any:
        return [] if v is None else v

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_dict_none(cls, v: Any) -> Any:
        return {} if v is None else v


class RegisterMcpServerRequest(BaseModel):
    """Request body for POST /api/targets/mcp-servers."""

    source: McpSource
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[McpCategory] = None
    upstream: Optional[McpUpstream] = None
    auth_method: Optional[McpAuthMethod] = Field(None, alias="authMethod")
    owners: list[Owner] = Field(default_factory=list)
    tags: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_custom_required(self) -> "RegisterMcpServerRequest":
        if self.source.type == McpSourceType.CUSTOM:
            if not self.name:
                raise ValueError("name is required for CUSTOM MCP servers")
            if not self.upstream:
                raise ValueError("upstream is required for CUSTOM MCP servers")
            if not self.category:
                raise ValueError("category is required for CUSTOM MCP servers")
        else:
            if not self.source.predefined_target_id:
                raise ValueError("source.predefinedTargetId is required for PREDEFINED MCP servers")
        return self


class EditMcpServerRequest(BaseModel):
    """Request body for PUT /api/targets/mcp-servers/{Id}.
    Allowed: description, owners, tags, and category (custom only).
    """

    description: Optional[str] = None
    category: Optional[McpCategory] = None
    owners: Optional[list[Owner]] = None
    tags: Optional[dict[str, str]] = None

    model_config = {"populate_by_name": True}


class McpServerStateRequest(BaseModel):
    state: McpState


class McpServerListResponse(BaseModel):
    mcp_servers: list[McpServerResponse] = Field(default_factory=list, alias="mcpServers")
    next_cursor: Optional[str] = Field(None, alias="nextCursor")

    model_config = {"populate_by_name": True}


class PredefinedMcpTarget(BaseModel):
    id: Optional[str] = None
    # The predefined catalog returns "version" while registered-target payloads
    # use "predefinedTargetVersion".  Accept both so the same model works for
    # both response shapes.
    predefined_target_version: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("predefinedTargetVersion", "version"),
        serialization_alias="predefinedTargetVersion",
    )
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[McpCategory] = None
    upstream: Optional[McpUpstream] = None
    # Predefined catalog returns authMethod as a plain string ("NONE",
    # "OAUTH2.1"); registered-target payloads return it as an object
    # {"type": "NONE"}.  Coerce the string form to the object form.
    auth_method: Optional[McpAuthMethod] = Field(None, alias="authMethod")
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    created_by: Optional[str] = Field(None, alias="createdBy")
    updated_by: Optional[str] = Field(None, alias="updatedBy")

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


class PredefinedMcpListResponse(BaseModel):
    targets: list[PredefinedMcpTarget] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error model (for parsing API error bodies)
# ---------------------------------------------------------------------------


class ApiError(BaseModel):
    code: Optional[str] = None
    message: Optional[str] = None
    description: Optional[str] = None
