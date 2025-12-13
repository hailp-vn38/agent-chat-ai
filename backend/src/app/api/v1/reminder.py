"""Reminder API Router - 6 endpoints for managing reminders by agent.

Endpoints:
1. POST /api/v1/agents/{agent_id}/reminders - Create reminder for agent
2. GET /api/v1/agents/{agent_id}/reminders - List reminders (paginated, filterable)
3. GET /api/v1/reminders/{reminder_id} - Get reminder detail
4. PATCH /api/v1/reminders/{reminder_id} - Update reminder
5. DELETE /api/v1/reminders/{reminder_id} - Soft delete reminder
6. POST /api/v1/reminders/{reminder_id}/received - Mark as received

Architecture:
- API layer handles HTTP validation and error formatting
- CRUD layer handles database operations with full error handling
- Dependencies validate user permissions and agent existence
- Timezone handling: User's timezone is canonical, server uses UTC for scheduling
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    NotFoundException,
)
from ...core.logger import get_logger
from ...crud.crud_reminders import crud_reminders
from ...crud.crud_agent import crud_agent
from ...models.reminder import ReminderStatus
from ...schemas.agent import AgentRead
from ...schemas.reminder import (
    ReminderCreate,
    ReminderListRead,
    ReminderRead,
    ReminderUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["reminders"])
reminder_detail_router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("/{agent_id}/reminders", response_model=ReminderRead, status_code=201)
async def create_reminder(
    agent_id: Annotated[str, Path(description="Agent ID (UUID)")],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    reminder_data: ReminderCreate,
) -> ReminderRead:
    """
    Create a new reminder for an agent and schedule it.

    Path Parameters:
    - agent_id: UUID (agent must belong to current user)

    Body:
    - content: string (1-5000 ký tự, bắt buộc)
    - title: string (max 255, optional)
    - remind_at: datetime ISO-8601 with timezone (bắt buộc, > now UTC)
    - reminder_metadata: dict (optional, max 10KB)

    Returns: ReminderRead

    Status Codes:
    - 201: Created
    - 400: Validation fail
    - 404: Agent not found
    """
    try:
        # Validate agent exists and belongs to current user
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )
        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Verify agent belongs to current user
        if agent.user_id != current_user.get("id"):
            raise NotFoundException("Agent not found (permission denied)")

        # Override agent_id from path (ignore any agent_id in body)
        reminder_data.agent_id = agent_id

        # Create reminder - all timezone conversion handled by CRUD layer
        reminder = await crud_reminders.create_reminder_from_dto(
            db=db,
            reminder_create=reminder_data,
        )

        return reminder

    except NotFoundException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating reminder: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}/reminders", response_model=PaginatedResponse[ReminderListRead])
async def list_reminders(
    agent_id: Annotated[str, Path(description="Agent ID (UUID)")],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    status: ReminderStatus | None = Query(None),
    q: str | None = Query(None, min_length=1, max_length=100),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    List reminders for an agent with pagination and filtering.

    Path Parameters:
    - agent_id: UUID (agent must belong to current user)

    Query Parameters:
    - status: enum (optional, filter by status)
    - q: string (optional, search in content/title)
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=10)

    Returns: PaginatedResponse[ReminderListRead]

    Status Codes:
    - 200: Success
    - 404: Agent not found
    """
    try:
        # Validate agent exists and belongs to current user
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )
        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        if agent.user_id != current_user.get("id"):
            raise NotFoundException("Agent not found (permission denied)")

        logger.debug(f"Listing reminders for agent {agent_id}")

        # List reminders by agent_id
        reminders_data = await crud_reminders.list_reminders_filtered(
            db=db,
            offset=(page - 1) * page_size,
            limit=page_size,
            agent_id=agent_id,
            status=status,
        )

        total = reminders_data["total_count"]
        total_pages = (total + page_size - 1) // page_size

        response = PaginatedResponse(
            success=True,
            message="Success",
            data=reminders_data["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        return response

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error listing reminders: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@reminder_detail_router.get("/{reminder_id}", response_model=ReminderRead)
async def get_reminder(
    reminder_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReminderRead:
    """
    Get reminder detail by ID.

    Path Parameters:
    - reminder_id: UUID (PK of reminder)

    Returns: SuccessResponse[ReminderRead]

    Status Codes:
    - 200: Success
    - 404: Reminder not found
    """
    try:
        reminder = await crud_reminders.get_reminder_by_id(
            db=db,
            reminder_id=reminder_id,
            include_deleted=False,
        )

        if reminder is None:
            raise NotFoundException("Reminder not found")

        return reminder

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error fetching reminder {reminder_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@reminder_detail_router.patch("/{reminder_id}", response_model=ReminderRead)
async def update_reminder(
    reminder_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    reminder_data: ReminderUpdate,
) -> ReminderRead:
    """
    Update reminder (only when status = pending).

    Path Parameters:
    - reminder_id: UUID (PK of reminder)

    Body:
    - content: string (optional)
    - title: string (optional)
    - remind_at: datetime (optional, > now)
    - reminder_metadata: dict (optional)

    Returns: SuccessResponse[ReminderRead]

    Status Codes:
    - 200: Success
    - 404: Reminder not found
    - 409: Status not pending
    """
    try:
        updated_reminder = await crud_reminders.update_reminder_safe(
            db=db,
            reminder_id=reminder_id,
            reminder_update=reminder_data,
        )
        return updated_reminder

    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundException(str(e))
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating reminder {reminder_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@reminder_detail_router.delete("/{reminder_id}", status_code=200)
async def delete_reminder(
    reminder_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, str]:
    """
    Soft delete reminder (set is_deleted=True).

    Path Parameters:
    - reminder_id: UUID (PK of reminder)

    Returns: SuccessResponse[dict]

    Status Codes:
    - 200: Success
    - 404: Reminder not found
    - 410: Reminder already deleted
    """
    try:
        await crud_reminders.soft_delete_reminder(
            db=db,
            reminder_id=reminder_id,
        )
        return {"message": "Reminder deleted successfully"}

    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundException(str(e))
        if "already deleted" in str(e).lower():
            raise HTTPException(status_code=410, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting reminder {reminder_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@reminder_detail_router.post("/{reminder_id}/received", response_model=ReminderRead)
async def mark_reminder_received(
    reminder_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReminderRead:
    """
    Mark reminder as received by device (status: delivered → received).

    Path Parameters:
    - reminder_id: UUID (PK of reminder)

    Returns: ReminderRead

    Status Codes:
    - 200: Success
    - 404: Reminder not found
    """
    try:
        updated_reminder = await crud_reminders.update_status_by_id(
            db=db,
            reminder_id=reminder_id,
            new_status=ReminderStatus.RECEIVED,
        )
        return updated_reminder

    except ValueError as e:
        if "not found" in str(e).lower():
            raise NotFoundException(str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking reminder {reminder_id} as received: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
