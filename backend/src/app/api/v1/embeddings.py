"""Embedding API endpoints."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, status

from ...core.config import settings
from ...schemas.embedding import EmbeddingData, EmbeddingRequest, EmbeddingResponse

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

LOGGER = logging.getLogger(__name__)


@router.post("", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """Generate embeddings for input text(s)."""
    try:
        if not request.input or (
            isinstance(request.input, list) and len(request.input) == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input cannot be empty",
            )

        model = request.model or settings.EMBEDDING_MODEL
        texts = [request.input] if isinstance(request.input, str) else request.input

        payload = {
            "inputs": texts,
            "input_type": "document",
            "embedding_model": model,
        }
        headers = {
            "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

        items = data.get("data") or data.get("embeddings")
        if not items:
            raise ValueError("Invalid response: missing 'data' or 'embeddings'")

        embeddings_list = [item["embedding"] for item in items]
        data_response = [
            EmbeddingData(index=i, embedding=emb)
            for i, emb in enumerate(embeddings_list)
        ]

        return EmbeddingResponse(model=model, data=data_response)

    except ValueError as e:
        LOGGER.error(f"Embedding error: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        LOGGER.exception(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embeddings",
        )
