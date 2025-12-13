"""
Agent schemas - Pydantic models for validation and serialization.
"""

from datetime import datetime
from typing import Annotated, Optional

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.enums import StatusEnum
from .device import DeviceRead
from .agent_template import AgentTemplateWithProvidersRead
from .template import TemplateWithProvidersRead


class MCPServerReference(BaseModel):
    """Reference to an MCP server (user-defined or config-based).

    Format:
    - db:{uuid} - User's MCP server from database
    - config:{name} - System MCP server from config.yml

    Example:
    - db:550e8400-e29b-41d4-a716-446655440000
    - config:filesystem
    - config:fetch
    """

    reference: Annotated[
        str,
        Field(
            pattern=r"^(db:[a-f0-9\-]{36}|config:[a-zA-Z0-9_\-]+)$",
            description="MCP server reference format: 'db:{uuid}' or 'config:{name}'",
            examples=["db:550e8400-e29b-41d4-a716-446655440000", "config:filesystem"],
        ),
    ]

    @property
    def source(self) -> str:
        """Get source type: 'user' or 'config'."""
        return "user" if self.reference.startswith("db:") else "config"

    @property
    def identifier(self) -> str:
        """Get the identifier (uuid for user, name for config)."""
        return self.reference.split(":", 1)[1]


class MCPSelection(BaseModel):
    """MCP server selection configuration for agent.

    Mode:
    - "all": Agent uses ALL available MCP servers (user + config)
    - "selected": Agent uses only selected MCP servers
    """

    mode: Annotated[str, Field(pattern="^(all|selected)$")] = "all"
    servers: Annotated[list[MCPServerReference] | None, Field(max_length=50)] = None

    @field_validator("servers", mode="before")
    @classmethod
    def validate_servers_required_if_selected(cls, v, info):
        """Validate that servers array is provided when mode is 'selected'."""
        if info.data.get("mode") == "selected" and not v:
            raise ValueError("servers array is required when mode is 'selected'")
        return v


class AgentBase(BaseModel):
    """Base agent schema with common fields."""

    agent_name: Annotated[
        str, Field(min_length=1, max_length=255, examples=["My AI Bot"])
    ]
    description: Annotated[str, Field(examples=["An intelligent chatbot agent"])]
    status: StatusEnum = Field(
        default=StatusEnum.disabled, examples=[StatusEnum.disabled]
    )
    user_profile: Annotated[
        str | None,
        Field(
            max_length=2000, default=None, examples=["Enthusiastic user who loves AI"]
        ),
    ] = None
    chat_history_conf: Annotated[
        int,
        Field(
            ge=0,
            le=2,
            default=1,
            description="Chat history config: 0=disabled, 1=text only, 2=text+audio",
        ),
    ] = 1


class AgentCreate(AgentBase):
    """Schema for creating a new agent (public API)."""

    model_config = ConfigDict(extra="forbid")


class AgentCreateInternal(AgentBase):
    """Internal schema for creating a new agent (with user_id)."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(examples=["550e8400-e29b-41d4-a716-446655440000"])


class AgentRead(AgentBase):
    """Schema for reading agent data."""

    id: str
    user_id: str
    active_template_id: str | None = None
    device_id: str | None = None
    device_mac_address: str | None = None
    user_profile: str | None = None
    chat_history_conf: int = 1
    created_at: datetime
    updated_at: datetime


class AgentWebhookRead(AgentRead):
    """Schema for reading agent data with webhook API key (internal use only)."""

    api_key: str | None = Field(
        default=None, description="Unique API key for webhook authentication"
    )


class AgentUpdate(BaseModel):
    """Schema for updating agent data."""

    model_config = ConfigDict(extra="ignore")

    agent_name: Annotated[str | None, Field(min_length=1, max_length=255, default=None)]
    description: Annotated[str | None, Field(default=None)]
    status: StatusEnum | None = Field(default=None)
    active_template_id: str | None = Field(default=None)
    device_id: str | None = Field(default=None)
    device_mac_address: str | None = Field(default=None, max_length=17)
    user_profile: Annotated[str | None, Field(max_length=2000, default=None)]
    chat_history_conf: Annotated[int | None, Field(ge=0, le=2, default=None)] = None


class AgentUpdateInternal(AgentUpdate):
    """Internal schema for updating agent (includes timestamp)."""

    updated_at: datetime


class AgentDelete(BaseModel):
    """Schema for deleting agent (soft delete)."""

    model_config = ConfigDict(extra="forbid")

    is_deleted: bool = Field(default=True, examples=[True])


class BindDeviceRequest(BaseModel):
    """Schema for binding device to agent."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            examples=["abc123def456"],
            description="Activation code from Redis",
        ),
    ]


class AgentDetailRead(BaseModel):
    """Schema for reading agent with full details (template, device, etc.)."""

    id: str
    user_id: str
    agent_name: str
    description: str
    status: StatusEnum
    active_template_id: str | None = None
    device_id: str | None = None
    device_mac_address: str | None = None
    created_at: datetime
    updated_at: datetime
    template: Optional[dict] = None  # Will be filled with Template data if exists
    device: Optional[dict] = None  # Will be filled with Device data if exists


class AgentWithDeviceAndTemplatesRead(BaseModel):
    """Schema for reading agent with device and templates list (with full provider info)."""

    agent: AgentRead
    device: Optional[DeviceRead] = None
    templates: list[TemplateWithProvidersRead] = Field(default_factory=list)


class WebhookConfig(BaseModel):
    """Schema for webhook API key response."""

    agent_id: str = Field(examples=["550e8400-e29b-41d4-a716-446655440000"])
    api_key: str | None = Field(
        default=None,
        examples=["dGVzdF9rZXlfdGhhdF9pc19sb25nX2Vub3VnaF9mb3Jfd2Vic29ja2V0X2F1dGg="],
    )

    model_config = ConfigDict(
        json_schema_extra={"description": "Webhook API key configuration"}
    )


class WebhookNotificationPayload(BaseModel):
    """Schema for webhook notification payload.

    This schema validates incoming webhook notifications that should be delivered
    to a device. The payload follows the same format as reminder notifications for
    consistency.

    Fields:
    - type: Must be exactly "notification"
    - useLLM: Whether to use LLM for processing the notification
    - title: Notification title (1-256 characters)
    - content: Notification content (1-2048 characters)

    Example:
    {
        "type": "notification",
        "useLLM": true,
        "title": "Alert from External System",
        "content": "This is a notification sent via webhook."
    }
    """

    type: Annotated[
        Literal["notification"],
        Field(description="Notification type identifier"),
    ] = "notification"
    useLLM: Annotated[
        bool,
        Field(description="Whether to use LLM for processing"),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description="Notification title",
            examples=["System Alert"],
        ),
    ]
    content: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2048,
            description="Notification content",
            examples=["This is a test notification."],
        ),
    ]

    model_config = ConfigDict(
        json_schema_extra={"description": "Webhook notification payload format"}
    )


class AgentMCPServerSelectedRead(BaseModel):
    """Schema for reading selected MCP server from agent_mcp_server_selected table."""

    id: str = Field(description="Selected MCP server record ID")
    agent_mcp_selection_id: str = Field(description="Parent selection record ID")
    reference: str = Field(description="MCP reference: 'db:{uuid}' or 'config:{name}'")
    mcp_name: str = Field(description="Resolved MCP server name")
    mcp_type: str = Field(description="MCP transport type: stdio, sse, or http")
    mcp_description: str | None = Field(default=None, description="MCP description")
    source: str = Field(description="MCP source: 'user' or 'config'")
    is_active: bool = Field(default=True, description="Whether MCP is active")
    resolved_at: datetime | None = Field(
        default=None, description="When metadata was last resolved"
    )
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)


class AgentMCPServerSelectedCreate(BaseModel):
    """Schema for creating selected MCP server record."""

    agent_mcp_selection_id: str = Field(description="Parent selection record ID")
    reference: str = Field(description="MCP reference: 'db:{uuid}' or 'config:{name}'")
    mcp_name: str = Field(description="Resolved MCP server name")
    mcp_type: str = Field(description="MCP transport type: stdio, sse, or http")
    mcp_description: str | None = Field(default=None, description="MCP description")
    source: str = Field(description="MCP source: 'user' or 'config'")
    is_active: bool = Field(default=True, description="Whether MCP is active")
    resolved_at: datetime | None = Field(
        default=None, description="When metadata was last resolved"
    )

    model_config = ConfigDict(extra="forbid")


class AgentMCPSelectionRead(BaseModel):
    """Schema for reading agent MCP selection with all selected servers and metadata."""

    id: str = Field(description="Selection record ID")
    agent_id: str = Field(description="Agent ID")
    mcp_selection_mode: str = Field(description="Selection mode: 'all' or 'selected'")
    servers: list[AgentMCPServerSelectedRead] = Field(
        default_factory=list,
        description="List of selected MCP servers with resolved metadata",
    )
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)


class AgentMCPSelectionCreate(BaseModel):
    """Schema for creating agent MCP selection."""

    agent_id: str = Field(description="Agent ID")
    mcp_selection_mode: str = Field(
        pattern="^(all|selected)$",
        default="all",
        description="Selection mode: 'all' or 'selected'",
    )

    model_config = ConfigDict(extra="forbid")
