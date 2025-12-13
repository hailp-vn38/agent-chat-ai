"""
Provider schemas - Pydantic models for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderCategory(str, Enum):
    """Supported provider categories."""

    LLM = "LLM"
    VLLM = "VLLM"
    TTS = "TTS"
    ASR = "ASR"
    MEMORY = "Memory"
    INTENT = "Intent"


class ProviderSourceFilter(str, Enum):
    """Filter providers by source."""

    ALL = "all"  # Both config and user providers
    CONFIG = "config"  # Only config.yml providers
    USER = "user"  # Only user-defined providers


class ProviderBase(BaseModel):
    """Base provider schema."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    category: ProviderCategory
    type: Annotated[str, Field(min_length=1, max_length=50)]
    config: dict[str, Any]
    is_active: bool = True


class ProviderCreate(ProviderBase):
    """Schema for creating a new provider."""

    model_config = ConfigDict(extra="forbid")


class ProviderCreateInternal(ProviderCreate):
    """Internal schema for creating provider (includes user_id)."""

    user_id: str


class ProviderRead(ProviderBase):
    """Schema for reading provider (masks secrets)."""

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False


class ProviderListItem(BaseModel):
    """Schema for provider list item - supports both user and config providers."""

    # Common fields
    reference: str = Field(
        description="Provider reference: 'db:{uuid}' or 'config:{name}'"
    )
    name: str
    category: str
    type: str
    config: dict[str, Any]
    source: str = Field(description="'user' or 'default'")
    permissions: list[str] = Field(
        description="Allowed actions: read, test, edit, delete"
    )
    is_active: bool = True

    # Optional fields (only present for user providers)
    id: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_deleted: bool | None = None


class ProviderUpdate(BaseModel):
    """Schema for updating provider."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=255, default=None)]
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class ProviderUpdateInternal(ProviderUpdate):
    """Internal schema for updating provider."""

    updated_at: datetime


class ProviderDelete(BaseModel):
    """Schema for deleting provider (soft delete)."""

    model_config = ConfigDict(extra="forbid")

    is_deleted: bool = True


# Provider Test Input/Output schemas
class ProviderTestInput(BaseModel):
    """Unified input data for provider testing.

    All fields are optional. When a field is not provided,
    the system uses default test data for that category.
    """

    # For ASR - audio to transcribe
    audio_base64: Annotated[
        str | None,
        Field(
            default=None,
            description="Base64-encoded audio data for ASR testing",
            max_length=14_000_000,  # ~10MB after base64 encoding
        ),
    ]
    audio_format: Annotated[
        str | None,
        Field(
            default=None,
            description="Audio format hint (wav, mp3, pcm). Auto-detected if not provided",
        ),
    ]

    # For TTS - text to synthesize
    text: Annotated[
        str | None,
        Field(
            default=None,
            description="Text content for TTS testing",
            max_length=1000,
        ),
    ]

    # For LLM - custom prompt
    prompt: Annotated[
        str | None,
        Field(
            default=None,
            description="Custom prompt for LLM testing",
            max_length=2000,
        ),
    ]

    # For VLLM - image + question
    image_base64: Annotated[
        str | None,
        Field(
            default=None,
            description="Base64-encoded image for VLLM testing",
            max_length=14_000_000,  # ~10MB after base64 encoding
        ),
    ]
    question: Annotated[
        str | None,
        Field(
            default=None,
            description="Question text for VLLM testing",
            max_length=1000,
        ),
    ]


class ProviderTestOutput(BaseModel):
    """Unified output schema for provider test results.

    Only relevant fields for the tested category will be populated.
    """

    # Text output (LLM, ASR, VLLM response)
    text: str | None = None

    # Audio output (TTS)
    audio_base64: str | None = None
    audio_format: str | None = None  # wav, mp3, ogg
    audio_size_bytes: int | None = None

    # Extensible metadata
    metadata: dict[str, Any] | None = None


# Provider Test schemas
class ProviderTestRequest(BaseModel):
    """Request schema for testing provider config."""

    category: ProviderCategory
    type: str
    config: dict[str, Any]
    input_data: ProviderTestInput | None = Field(
        default=None,
        description="Optional custom input data for testing. If not provided, uses default test data.",
    )


class ProviderTestResult(BaseModel):
    """Result of provider test."""

    success: bool
    message: str | None = None
    error: str | None = None
    error_code: str | None = None
    latency_ms: int | None = None
    output: ProviderTestOutput | None = None


class ProviderTestResponse(BaseModel):
    """Response schema for provider test."""

    valid: bool
    normalized_config: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    test_result: ProviderTestResult | None = None


class ProviderValidateRequest(BaseModel):
    """Request schema for validating provider config (without API test)."""

    category: ProviderCategory
    type: str
    config: dict[str, Any]


class ProviderValidateResponse(BaseModel):
    """Response schema for provider validation."""

    valid: bool
    normalized_config: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


# Provider Reference validation schemas
class ProviderReferenceValidateRequest(BaseModel):
    """Request schema for validating provider reference format."""

    category: ProviderCategory
    reference: str = Field(
        description="Provider reference to validate. Format: 'config:{name}' or 'db:{uuid}'"
    )


class ProviderReferenceResolvedInfo(BaseModel):
    """Resolved provider info from reference."""

    name: str
    type: str
    source: str  # "user" or "default"


class ProviderReferenceValidateResponse(BaseModel):
    """Response schema for provider reference validation."""

    valid: bool
    reference: str
    resolved: ProviderReferenceResolvedInfo | None = None
    errors: list[str] = Field(default_factory=list)


# Provider Test by Reference schemas
class ProviderTestByReferenceRequest(BaseModel):
    """Request schema for testing provider by reference."""

    reference: str = Field(
        description="Provider reference to test. Format: 'config:{name}' or 'db:{uuid}'"
    )
    input_data: ProviderTestInput | None = Field(
        default=None,
        description="Optional custom input data for testing. If not provided, uses default test data.",
    )


class ProviderTestByReferenceResponse(BaseModel):
    """Response schema for provider test by reference."""

    valid: bool
    reference: str
    source: str | None = None  # "user" or "default"
    category: str | None = None
    type: str | None = None
    errors: list[str] = Field(default_factory=list)
    test_result: ProviderTestResult | None = None
