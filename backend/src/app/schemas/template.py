"""
Template schemas - Pydantic models for validation and serialization.

Templates are now independent and shareable across multiple agents.

Provider fields (ASR, LLM, VLLM, TTS, Memory, Intent) accept provider reference format:
- "config:{name}" - Provider from config.yml (e.g., "config:CopilotLLM")
- "db:{uuid}" - Provider from database (e.g., "db:019abc-def...")
- "{uuid}" - Backward compatible, auto-normalized to "db:{uuid}"
- null - Fallback to selected_module in config.yml

Tools field accepts list of tool references:
- UserTool UUIDs - Reference to user's tool configs
- Tool names - System tools from all_function_registry
- Empty list/null - Fallback to config["Intent"]["functions"]
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.module_factory import normalize_provider_reference


class TemplateBase(BaseModel):
    """Base template schema."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    prompt: Annotated[str, Field(examples=["You are a helpful AI assistant."])]


class TemplateCreate(TemplateBase):
    """Schema for creating a new template (client-facing).

    Provider fields accept provider reference format:
    - "config:{name}" - Provider from config.yml
    - "db:{uuid}" - Provider from database
    - "{uuid}" - Backward compat, auto-normalized to "db:{uuid}"
    - null - Fallback to selected_module
    """

    model_config = ConfigDict(extra="forbid")

    # Provider references
    ASR: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="ASR provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
            examples=[
                "config:VietNamASRLocal",
                "db:01234567-89ab-cdef-0123-456789abcdef",
            ],
        ),
    ] = None
    LLM: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="LLM provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
            examples=["config:CopilotLLM", "db:01234567-89ab-cdef-0123-456789abcdef"],
        ),
    ] = None
    VLLM: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="VLLM provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    TTS: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="TTS provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
            examples=[
                "config:HoaiMyEdgeTTS",
                "db:01234567-89ab-cdef-0123-456789abcdef",
            ],
        ),
    ] = None
    Memory: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Memory provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
            examples=["config:nomem"],
        ),
    ] = None
    Intent: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Intent provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
            examples=["config:function_call"],
        ),
    ] = None
    summary_memory: str | None = None

    # Tool references - list of UserTool UUIDs or system tool names
    tools: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Tool references: list of UserTool UUIDs or system tool names. NULL/empty = use config default",
            examples=[
                [
                    "create_reminder",
                    "get_weather",
                    "01234567-89ab-cdef-0123-456789abcdef",
                ]
            ],
        ),
    ] = None

    # Sharing flag
    is_public: bool = Field(default=False)

    @field_validator("ASR", "LLM", "VLLM", "TTS", "Memory", "Intent", mode="before")
    @classmethod
    def validate_provider_reference(cls, v: str | None) -> str | None:
        """Validate and normalize provider reference format."""
        if v is None:
            return None
        return normalize_provider_reference(v)


class TemplateCreateInternal(TemplateCreate):
    """Schema for creating template (internal - includes user_id)."""

    user_id: str


class TemplateRead(TemplateBase):
    """Schema for reading template."""

    id: str
    user_id: str
    ASR: str | None = None
    LLM: str | None = None
    VLLM: str | None = None
    TTS: str | None = None
    Memory: str | None = None
    Intent: str | None = None
    tools: list[str] | None = None
    summary_memory: str | None = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime


class ProviderInfo(BaseModel):
    """Provider info for template response with source indication."""

    reference: str  # "config:name" or "db:uuid"
    name: str
    type: str
    source: str  # "user" or "default"

    # Optional: only present for user providers
    id: str | None = None


class TemplateWithProvidersRead(TemplateBase):
    """Schema for reading template with full provider info."""

    id: str
    user_id: str
    tools: list[str] | None = None
    summary_memory: str | None = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime

    # Provider info (reference, name, type, source) instead of just ID
    ASR: ProviderInfo | None = None
    LLM: ProviderInfo | None = None
    VLLM: ProviderInfo | None = None
    TTS: ProviderInfo | None = None
    Memory: ProviderInfo | None = None
    Intent: ProviderInfo | None = None


class TemplateWithAgentsCountRead(TemplateWithProvidersRead):
    """Schema for reading template with count of assigned agents."""

    agents_count: int = 0


class TemplateUpdate(BaseModel):
    """Schema for updating template.

    Provider fields accept provider reference format:
    - "config:{name}" - Provider from config.yml
    - "db:{uuid}" - Provider from database
    - "{uuid}" - Backward compat, auto-normalized to "db:{uuid}"
    - null - Fallback to selected_module
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=255, default=None)]
    prompt: str | None = None
    summary_memory: str | None = None
    is_public: bool | None = None

    # Provider references
    ASR: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="ASR provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    LLM: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="LLM provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    VLLM: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="VLLM provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    TTS: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="TTS provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    Memory: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Memory provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None
    Intent: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description="Intent provider reference. Format: 'config:{name}' or 'db:{uuid}'. NULL = use config.yml default",
        ),
    ] = None

    # Tool references
    tools: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Tool references: list of UserTool UUIDs or system tool names. NULL/empty = use config default",
        ),
    ] = None

    @field_validator("ASR", "LLM", "VLLM", "TTS", "Memory", "Intent", mode="before")
    @classmethod
    def validate_provider_reference(cls, v: str | None) -> str | None:
        """Validate and normalize provider reference format."""
        if v is None:
            return None
        return normalize_provider_reference(v)


class TemplateUpdateInternal(TemplateUpdate):
    """Internal schema for updating template (includes timestamp)."""

    updated_at: datetime


class TemplateDelete(BaseModel):
    """Schema for deleting template (soft delete)."""

    model_config = ConfigDict(extra="forbid")

    is_deleted: bool = Field(default=True)
