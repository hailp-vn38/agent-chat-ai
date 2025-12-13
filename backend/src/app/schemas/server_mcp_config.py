"""
ServerMCPConfig schemas - Pydantic models for MCP server configuration.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCPToolInfo(BaseModel):
    """Information about a tool from MCP server."""

    name: str = Field(description="Tool name")
    description: str | None = Field(None, description="Tool description")
    inputSchema: dict | None = Field(None, description="JSON schema for tool input")

    model_config = ConfigDict(from_attributes=True)


class MCPSourceFilter(str, Enum):
    """Filter MCP servers by source."""

    ALL = "all"  # Both config and user MCP servers
    CONFIG = "config"  # Only config.yml MCP servers
    USER = "user"  # Only user-defined MCP servers


class MCPReference(BaseModel):
    """Reference to an MCP server (user or config).

    Format:
    - db:{uuid} - User-defined MCP server from database
    - config:{name} - System MCP server from config.yml
    """

    reference: str = Field(
        description="MCP server reference: 'db:{uuid}' or 'config:{name}'",
        pattern=r"^(db:[a-f0-9\-]{36}|config:[a-zA-Z0-9_\-]+)$",
    )

    @property
    def source(self) -> str:
        """Get source type (user or config)."""
        return "user" if self.reference.startswith("db:") else "config"

    @property
    def identifier(self) -> str:
        """Get identifier (uuid or config name)."""
        return self.reference.split(":", 1)[1]


class MCPListItem(BaseModel):
    """Schema for MCP server list item - supports both user and config servers."""

    # Common fields
    reference: str = Field(
        description="MCP server reference: 'db:{uuid}' or 'config:{name}'"
    )
    name: str
    description: str | None = None
    type: str
    source: str = Field(description="'user' or 'config'")
    permissions: list[str] = Field(
        description="Allowed actions: read, test, edit, delete"
    )
    is_active: bool = True

    # Optional fields (only present for user MCP servers)
    id: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TransportTypeEnum(str, Enum):
    """MCP transport type."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class ServerMCPConfigBase(BaseModel):
    """Base schema for MCP server config."""

    name: Annotated[str, Field(min_length=3, max_length=255, pattern="^[a-z0-9_]+$")]
    description: Annotated[str | None, Field(max_length=1000)] = None
    type: TransportTypeEnum
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """Validate name is snake_case."""
        if not v.islower() or not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Name must be lowercase snake_case (a-z, 0-9, _)")
        return v


class ServerMCPConfigCreate(ServerMCPConfigBase):
    """Schema for creating a new MCP config."""

    # Stdio-specific
    command: Annotated[str | None, Field(max_length=255)] = None
    args: Annotated[list[str] | None, Field(max_length=50)] = None
    env: Annotated[dict[str, str] | None, Field()] = None

    # SSE/HTTP-specific
    url: Annotated[str | None, Field(max_length=2048)] = None
    headers: Annotated[dict[str, str] | None, Field()] = None

    # Tools metadata
    tools: Annotated[list[MCPToolInfo] | None, Field(max_length=100)] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate transport type."""
        if isinstance(v, str):
            v = v.lower()
        return v

    @field_validator("*", mode="before")
    @classmethod
    def validate_required_fields(cls, v, info):
        """Validate that required fields are set based on type."""
        if info.field_name == "command" or info.field_name == "url":
            return v

        # Get type from data
        data = info.data
        config_type = data.get("type")

        if info.field_name == "command" and config_type == TransportTypeEnum.STDIO:
            if v is None and info.data.get("command") is None:
                raise ValueError("command is required for stdio transport")
        elif info.field_name == "url" and config_type in (
            TransportTypeEnum.SSE,
            TransportTypeEnum.HTTP,
        ):
            if v is None and info.data.get("url") is None:
                raise ValueError("url is required for sse/http transport")

        return v


class ServerMCPConfigCreateInternal(ServerMCPConfigCreate):
    """Schema for creating MCP config with user_id (internal use only)."""

    user_id: str
    tools_last_synced_at: datetime | None = None


class ServerMCPConfigRead(ServerMCPConfigBase):
    """Schema for reading MCP config."""

    id: str
    user_id: str
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    tools: list[MCPToolInfo] | None = None
    tools_last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False

    model_config = ConfigDict(from_attributes=True)


class ServerMCPConfigUpdate(BaseModel):
    """Schema for updating MCP config."""

    description: Annotated[str | None, Field(max_length=1000)] = None
    is_active: bool | None = None
    command: Annotated[str | None, Field(max_length=255)] = None
    args: Annotated[list[str] | None, Field(max_length=50)] = None
    env: Annotated[dict[str, str] | None, Field()] = None
    url: Annotated[str | None, Field(max_length=2048)] = None
    headers: Annotated[dict[str, str] | None, Field()] = None
    tools: Annotated[list[MCPToolInfo] | None, Field(max_length=100)] = None

    model_config = ConfigDict(extra="forbid")


class ServerMCPConfigDelete(BaseModel):
    """Schema for deleting MCP config (soft delete)."""

    pass


class ServerMCPConfigTestResponse(BaseModel):
    """Response for testing MCP config connection."""

    success: bool
    message: str
    name: str | None = None
    tools: list[MCPToolInfo] | None = None
    error: str | None = None


class ServerMCPConfigRefreshResponse(BaseModel):
    """Response for refreshing tools from MCP server."""

    success: bool
    message: str
    data: dict | None = None
    error: str | None = None


class ToolChanges(BaseModel):
    """Changes detected in tools after refresh."""

    added: list[MCPToolInfo] = Field(default_factory=list)
    removed: list[MCPToolInfo] = Field(default_factory=list)
    updated: list[dict] = Field(
        default_factory=list, description="List of {old, new} tool pairs"
    )

    model_config = ConfigDict(from_attributes=True)


class ConfigMCPServerRead(BaseModel):
    """Schema for reading config-based MCP server (from JSON file)."""

    name: str = Field(description="MCP server name (key in mcpServers)")
    type: str = Field(description="Transport type: stdio, sse, http")
    description: str | None = Field(default=None, description="Server description")
    source: str = Field(
        default="config", description="Always 'config' for these servers"
    )
    is_active: bool = Field(default=True)
    url: str | None = Field(default=None, description="URL for SSE/HTTP transport")
    command: str | None = Field(default=None, description="Command for stdio transport")

    model_config = ConfigDict(from_attributes=True)
