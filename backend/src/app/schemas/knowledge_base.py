"""
Knowledge Base schemas - Pydantic models for validation and serialization.

Defines request/response schemas for Knowledge Base API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MemorySector(str, Enum):
    """OpenMemory sector types for categorizing knowledge."""

    EPISODIC = "episodic"  # Events and experiences
    SEMANTIC = "semantic"  # Facts and knowledge
    PROCEDURAL = "procedural"  # Habits and workflows
    EMOTIONAL = "emotional"  # Feelings and sentiment
    REFLECTIVE = "reflective"  # Meta-thoughts and insights


# ==================== Request Schemas ====================


class KBItemCreate(BaseModel):
    """Schema for creating a new knowledge base entry."""

    model_config = ConfigDict(extra="forbid")

    content: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50000,
            description="Knowledge content text",
            examples=["Python is a programming language"],
        ),
    ]
    sector: MemorySector = Field(
        default=MemorySector.SEMANTIC,
        description="Memory sector for categorization",
        examples=[MemorySector.SEMANTIC],
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for filtering and organization",
        examples=[["python", "programming"]],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
        examples=[{"source": "manual"}],
    )


class KBItemUpdate(BaseModel):
    """Schema for updating an existing knowledge base entry."""

    model_config = ConfigDict(extra="forbid")

    content: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=50000,
            default=None,
            description="Updated content text",
        ),
    ] = None
    tags: list[str] | None = Field(
        default=None,
        max_length=20,
        description="Updated tags list",
    )


class KBSearchRequest(BaseModel):
    """Schema for semantic search in knowledge base."""

    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1000,
            description="Search query",
            examples=["What is Python?"],
        ),
    ]
    k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return",
    )
    min_score: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Minimum similarity score threshold",
    )
    sector: MemorySector | None = Field(
        default=None,
        description="Filter by sector",
    )


class KBIngestFileRequest(BaseModel):
    """Schema for file ingestion request."""

    model_config = ConfigDict(extra="forbid")

    content_type: Literal["pdf", "docx", "txt", "md"] = Field(
        description="File content type",
        examples=["pdf"],
    )
    data: str = Field(
        description="Base64 encoded file content",
        min_length=1,
    )
    filename: str = Field(
        description="Original filename",
        min_length=1,
        max_length=255,
        examples=["document.pdf"],
    )
    sector: MemorySector = Field(
        default=MemorySector.SEMANTIC,
        description="Memory sector for ingested content",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for ingested content",
    )


class KBIngestURLRequest(BaseModel):
    """Schema for URL ingestion request."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl = Field(
        description="URL to crawl and ingest",
        examples=["https://example.com/article"],
    )
    sector: MemorySector = Field(
        default=MemorySector.SEMANTIC,
        description="Memory sector for ingested content",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for ingested content",
    )


# ==================== Response Schemas ====================


class KBItemRead(BaseModel):
    """Schema for reading a knowledge base entry."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique memory ID")
    content: str = Field(description="Memory content")
    sectors: list[MemorySector] = Field(
        default_factory=list,
        description="Memory sectors (can belong to multiple)",
    )
    primary_sector: MemorySector = Field(
        default=MemorySector.SEMANTIC,
        description="Primary sector",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Memory tags",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Memory metadata",
    )
    salience: float | None = Field(
        default=None,
        description="Importance score (0-1)",
    )
    last_seen_at: int | None = Field(
        default=None,
        description="Last access timestamp (Unix ms)",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Creation timestamp",
    )


class KBSearchResult(BaseModel):
    """Schema for a search result item."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Memory ID")
    content: str = Field(description="Memory content")
    score: float = Field(description="Similarity score")
    sectors: list[MemorySector] = Field(
        default_factory=list,
        description="Memory sectors",
    )
    primary_sector: MemorySector = Field(
        default=MemorySector.SEMANTIC,
        description="Primary sector",
    )
    path: list[str] = Field(
        default_factory=list,
        description="Navigation path",
    )
    salience: float | None = Field(
        default=None,
        description="Importance score",
    )
    last_seen_at: int | None = Field(
        default=None,
        description="Last access timestamp (Unix ms)",
    )


class KBSearchResponse(BaseModel):
    """Schema for search response."""

    query: str = Field(description="Original search query")
    matches: list[KBSearchResult] = Field(
        default_factory=list,
        description="Search results",
    )
    total: int = Field(
        default=0,
        description="Total number of matches",
    )


class KBIngestResponse(BaseModel):
    """Schema for ingestion response."""

    success: bool = Field(description="Whether ingestion was successful")
    message: str = Field(description="Status message")
    items_created: int = Field(
        default=0,
        description="Number of items created",
    )


class KBHealthResponse(BaseModel):
    """Schema for health check response."""

    status: str = Field(description="Service status")
    version: str | None = Field(
        default=None,
        description="Service version",
    )
    message: str | None = Field(
        default=None,
        description="Status message",
    )


class KBSectorInfo(BaseModel):
    """Schema for sector information."""

    name: str = Field(description="Sector name")
    description: str = Field(description="Sector description")


class KBSectorsResponse(BaseModel):
    """Schema for sectors list response."""

    sectors: list[KBSectorInfo] = Field(
        default_factory=list,
        description="Available sectors",
    )


# ==================== List Response ====================


class KBListResponse(BaseModel):
    """Schema for paginated list response."""

    items: list[KBItemRead] = Field(
        default_factory=list,
        description="List of memory items",
    )
    total: int = Field(
        default=0,
        description="Total number of items",
    )
    limit: int = Field(description="Items per page")
    offset: int = Field(description="Current offset")
