"""Schemas for embedding endpoints."""

from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request schema for embedding endpoint (OpenAI-compatible)."""

    input: str | list[str] = Field(
        ...,
        description="Text or list of texts to embed",
        examples=["Hello world", ["Hello", "World"]],
    )
    model: str | None = Field(
        default=None,
        description="Model to use for embedding (optional, uses default from config)",
    )
    dimensions: int | None = Field(
        default=None,
        description="Number of dimensions for the embedding vector (optional)",
    )


class EmbeddingData(BaseModel):
    """Single embedding result."""

    index: int = Field(..., description="Index of the input text")
    embedding: list[float] = Field(..., description="Embedding vector")


class EmbeddingResponse(BaseModel):
    """Response schema for embedding endpoint."""

    model: str = Field(..., description="Model used for embedding")
    data: list[EmbeddingData] = Field(..., description="List of embeddings")
