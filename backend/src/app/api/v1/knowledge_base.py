"""Knowledge Base API router.

Exposes endpoints for managing knowledge base entries per agent:
- CRUD operations for knowledge items
- Semantic search
- File and URL ingestion
- Health check and sector listing

All endpoints require authentication and agent ownership validation.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
)
from ...core.logger import get_logger
from ...crud.crud_agent import crud_agent
from ...schemas.agent import AgentRead
from ...schemas.base import SuccessResponse
from ...schemas.knowledge_base import (
    KBHealthResponse,
    KBIngestFileRequest,
    KBIngestResponse,
    KBIngestURLRequest,
    KBItemCreate,
    KBItemRead,
    KBItemUpdate,
    KBListResponse,
    KBSearchRequest,
    KBSearchResponse,
    KBSearchResult,
    KBSectorInfo,
    KBSectorsResponse,
    MemorySector,
)
from ...services.openmemory import (
    OpenMemoryError,
    OpenMemoryNotFoundError,
    OpenMemoryUnavailableError,
    get_openmemory_service,
)

logger = get_logger(__name__)

router = APIRouter(tags=["knowledge-base"])


# ==================== Helper Functions ====================


async def require_openmemory_enabled() -> None:
    """
    Dependency để kiểm tra OpenMemory service có được bật không.

    Raises:
        HTTPException: 503 nếu OpenMemory bị disabled
    """
    if not settings.openmemory.enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "Knowledge Base feature is disabled. "
                "Set OPENMEMORY_ENABLED=true in environment variables to enable."
            ),
        )


async def verify_agent_ownership(
    db: AsyncSession,
    agent_id: str,
    user_id: str,
) -> AgentRead:
    """
    Verify that the user owns the specified agent.

    Args:
        db: Database session
        agent_id: Agent UUID
        user_id: User UUID

    Returns:
        AgentRead: Agent data

    Raises:
        NotFoundException: Agent not found
        ForbiddenException: User doesn't own the agent
    """
    agent = await crud_agent.get(
        db=db,
        id=agent_id,
        schema_to_select=AgentRead,
        return_as_model=True,
    )

    if not agent:
        raise NotFoundException(f"Agent {agent_id} not found")

    if agent.user_id != user_id:
        raise ForbiddenException("You don't have access to this agent")

    return agent


def handle_openmemory_error(e: OpenMemoryError) -> None:
    """Convert OpenMemory errors to HTTP exceptions."""
    if isinstance(e, OpenMemoryUnavailableError):
        raise ServiceUnavailableException(
            "Knowledge base service is unavailable. Please try again later."
        )
    elif isinstance(e, OpenMemoryNotFoundError):
        raise NotFoundException("Knowledge base item not found")
    else:
        logger.error(f"OpenMemory error: {e.message}")
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=e.message,
        )


def parse_memory_to_item(memory: dict) -> KBItemRead:
    """Parse OpenMemory response to KBItemRead schema."""
    sectors = memory.get("sectors", [])
    if not sectors and "metadata" in memory:
        sector = memory["metadata"].get("sector", "semantic")
        sectors = [sector]

    primary_sector = memory.get("primary_sector", sectors[0] if sectors else "semantic")

    return KBItemRead(
        id=memory.get("id", ""),
        content=memory.get("content", ""),
        sectors=[
            MemorySector(s) for s in sectors if s in MemorySector._value2member_map_
        ],
        primary_sector=(
            MemorySector(primary_sector)
            if primary_sector in MemorySector._value2member_map_
            else MemorySector.SEMANTIC
        ),
        tags=memory.get("tags", []),
        metadata=memory.get("metadata", {}),
        salience=memory.get("salience"),
        last_seen_at=memory.get("last_seen_at"),
        created_at=memory.get("created_at"),
    )


def parse_memory_to_search_result(match: dict) -> KBSearchResult:
    """Parse OpenMemory search match to KBSearchResult schema."""
    sectors = match.get("sectors", [])
    primary_sector = match.get("primary_sector", sectors[0] if sectors else "semantic")

    return KBSearchResult(
        id=match.get("id", ""),
        content=match.get("content", ""),
        score=match.get("score", 0.0),
        sectors=[
            MemorySector(s) for s in sectors if s in MemorySector._value2member_map_
        ],
        primary_sector=(
            MemorySector(primary_sector)
            if primary_sector in MemorySector._value2member_map_
            else MemorySector.SEMANTIC
        ),
        path=match.get("path", []),
        salience=match.get("salience"),
        last_seen_at=match.get("last_seen_at"),
    )


# ==================== Health & Info Endpoints ====================


@router.get(
    "/knowledge-base/health",
    response_model=SuccessResponse[KBHealthResponse],
    summary="Check OpenMemory health",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def check_health(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SuccessResponse[KBHealthResponse]:
    """
    Check OpenMemory service health status.

    Returns service status, version, and message.
    """
    service = get_openmemory_service()

    try:
        health = await service.health_check()
        return SuccessResponse(
            data=KBHealthResponse(
                status=health.get("status", "ok"),
                version=health.get("version"),
                message=health.get("message"),
            )
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.get(
    "/knowledge-base/sectors",
    response_model=SuccessResponse[KBSectorsResponse],
    summary="Get available memory sectors",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def get_sectors(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> SuccessResponse[KBSectorsResponse]:
    """
    Get list of available memory sectors with descriptions.

    Sectors categorize knowledge entries by type:
    - episodic: Events and experiences
    - semantic: Facts and knowledge
    - procedural: Habits and workflows
    - emotional: Feelings and sentiment
    - reflective: Meta-thoughts and insights
    """
    sector_descriptions = {
        "episodic": "Events and experiences (sự kiện, trải nghiệm)",
        "semantic": "Facts and knowledge (kiến thức, sự thật)",
        "procedural": "Habits and workflows (quy trình, thói quen)",
        "emotional": "Feelings and sentiment (cảm xúc)",
        "reflective": "Meta-thoughts and insights (suy nghĩ, nhận định)",
    }

    sectors = [
        KBSectorInfo(
            name=sector.value, description=sector_descriptions.get(sector.value, "")
        )
        for sector in MemorySector
    ]

    return SuccessResponse(data=KBSectorsResponse(sectors=sectors))


# ==================== CRUD Endpoints ====================


@router.post(
    "/agents/{agent_id}/knowledge-base/items",
    response_model=SuccessResponse[KBItemRead],
    summary="Add knowledge entry",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def add_item(
    agent_id: str,
    item: KBItemCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBItemRead]:
    """
    Add a new knowledge entry to agent's knowledge base.

    The entry is stored in OpenMemory with agent_id as user_id for isolation.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        memory = await service.add_memory(
            agent_id=agent_id,
            content=item.content,
            sector=item.sector.value,
            tags=item.tags,
            metadata=item.metadata,
        )

        return SuccessResponse(
            data=parse_memory_to_item(memory),
            message="Knowledge entry added successfully",
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.get(
    "/agents/{agent_id}/knowledge-base/items",
    response_model=SuccessResponse[KBListResponse],
    summary="List knowledge entries",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def list_items(
    agent_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sector: MemorySector | None = None,
) -> SuccessResponse[KBListResponse]:
    """
    List knowledge entries for an agent with pagination.

    Supports optional filtering by sector.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        response = await service.list_memories(
            agent_id=agent_id,
            limit=limit,
            offset=offset,
            sector=sector.value if sector else None,
        )

        items = [parse_memory_to_item(m) for m in response.get("items", [])]

        return SuccessResponse(
            data=KBListResponse(
                items=items,
                total=response.get("total", len(items)),
                limit=limit,
                offset=offset,
            )
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.get(
    "/agents/{agent_id}/knowledge-base/items/{item_id}",
    response_model=SuccessResponse[KBItemRead],
    summary="Get knowledge entry",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def get_item(
    agent_id: str,
    item_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBItemRead]:
    """
    Get a single knowledge entry by ID.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        memory = await service.get_memory(item_id)
        return SuccessResponse(data=parse_memory_to_item(memory))
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.patch(
    "/agents/{agent_id}/knowledge-base/items/{item_id}",
    response_model=SuccessResponse[KBItemRead],
    summary="Update knowledge entry",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def update_item(
    agent_id: str,
    item_id: str,
    item: KBItemUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBItemRead]:
    """
    Update an existing knowledge entry.

    Only provided fields will be updated.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        memory = await service.update_memory(
            memory_id=item_id,
            agent_id=agent_id,
            content=item.content,
            tags=item.tags,
        )

        return SuccessResponse(
            data=parse_memory_to_item(memory),
            message="Knowledge entry updated successfully",
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.delete(
    "/agents/{agent_id}/knowledge-base/items/{item_id}",
    response_model=SuccessResponse[dict],
    summary="Delete knowledge entry",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def delete_item(
    agent_id: str,
    item_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[dict]:
    """
    Delete a knowledge entry.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        await service.delete_memory(item_id, agent_id)
        return SuccessResponse(
            data={"id": item_id, "deleted": True},
            message="Knowledge entry deleted successfully",
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


# ==================== Search Endpoint ====================


@router.post(
    "/agents/{agent_id}/knowledge-base/search",
    response_model=SuccessResponse[KBSearchResponse],
    summary="Search knowledge base",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def search(
    agent_id: str,
    request: KBSearchRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBSearchResponse]:
    """
    Semantic search in agent's knowledge base.

    Returns ranked results based on similarity to the query.
    Supports filtering by sector and minimum score threshold.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        response = await service.query_memory(
            agent_id=agent_id,
            query=request.query,
            k=request.k,
            min_score=request.min_score,
            sector=request.sector.value if request.sector else None,
        )

        # Extract matches from response dict
        matches = response.get("matches", [])
        results = [parse_memory_to_search_result(m) for m in matches]

        return SuccessResponse(
            data=KBSearchResponse(
                query=request.query,
                matches=results,
                total=len(results),
            )
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


# ==================== Ingestion Endpoints ====================


@router.post(
    "/agents/{agent_id}/knowledge-base/ingest/file",
    response_model=SuccessResponse[KBIngestResponse],
    summary="Ingest file",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def ingest_file(
    agent_id: str,
    request: KBIngestFileRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBIngestResponse]:
    """
    Upload and ingest a document file into the knowledge base.

    Supported formats: PDF, DOCX, TXT, MD

    The file content should be base64 encoded.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        result = await service.ingest_file(
            agent_id=agent_id,
            content_type=request.content_type,
            data=request.data,
            filename=request.filename,
            sector=request.sector.value,
            tags=request.tags,
        )

        return SuccessResponse(
            data=KBIngestResponse(
                success=True,
                message=f"File '{request.filename}' ingested successfully",
                items_created=result.get("items_created", 0),
            )
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)


@router.post(
    "/agents/{agent_id}/knowledge-base/ingest/url",
    response_model=SuccessResponse[KBIngestResponse],
    summary="Ingest URL",
    dependencies=[Depends(require_openmemory_enabled)],
)
async def ingest_url(
    agent_id: str,
    request: KBIngestURLRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[KBIngestResponse]:
    """
    Crawl and ingest content from a URL into the knowledge base.
    """
    await verify_agent_ownership(db, agent_id, current_user["id"])

    service = get_openmemory_service()

    try:
        result = await service.ingest_url(
            agent_id=agent_id,
            url=str(request.url),
            sector=request.sector.value,
            tags=request.tags,
        )

        return SuccessResponse(
            data=KBIngestResponse(
                success=True,
                message=f"URL '{request.url}' ingested successfully",
                items_created=result.get("items_created", 0),
            )
        )
    except OpenMemoryError as e:
        handle_openmemory_error(e)
