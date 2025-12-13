"""Reminder schemas - Pydantic models for validation and serialization.

Pattern: Separate schemas for create (input), read (output), update, and list operations.
Uses Pydantic V2 with Field, Annotated for validation.
"""

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..core.logger import get_logger
from ..models.reminder import ReminderStatus

logger = get_logger(__name__)


# ============ Base Schemas ============


class ReminderBase(BaseModel):
    """Base reminder schema with common fields."""

    content: Annotated[
        str,
        Field(
            min_length=1,
            max_length=5000,
            description="Nội dung nhắc nhở (1-5000 ký tự)",
            examples=["Hãy uống nước!"],
        ),
    ]
    title: Annotated[
        Optional[str],
        Field(
            max_length=255,
            default=None,
            description="Tiêu đề nhắc nhở (optional, max 255 ký tự)",
            examples=["Nhắc nhở uống nước"],
        ),
    ] = None


# ============ Create Schemas ============


class ReminderCreate(ReminderBase):
    """Schema for creating a new reminder (POST /agents/{agent_id}/reminders).

    agent_id is optional in request body (will be set from URL path parameter).
    """

    agent_id: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Agent ID (UUID, optional - will be set from URL path)",
            examples=["550e8400-e29b-41d4-a716-446655440000"],
        ),
    ] = None
    remind_at: Annotated[
        datetime,
        Field(
            description="Thời gian nhắc nhở (ISO-8601 with timezone, phải > now UTC)",
            examples=["2025-10-28T10:30:00+07:00"],
        ),
    ]
    reminder_metadata: Annotated[
        Optional[dict],
        Field(
            default=None,
            max_length=10240,  # 10KB limit
            description="Dữ liệu bổ sung (optional, max 10KB)",
            examples=[{"priority": "high", "category": "health"}],
        ),
    ] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("remind_at", mode="after")
    @classmethod
    def validate_remind_at(cls, v: datetime) -> datetime:
        """Validate that remind_at is in the future (UTC).

        Accepts ISO-8601 format with or without timezone:
        - "2025-10-28T10:30:00+07:00" → parsed with +07:00 offset
        - "2025-10-28T10:30:00Z" → parsed as UTC
        - "2025-10-28T10:30:00" → treated as UTC if no TZ info
        """
        from datetime import timezone as tz

        now = datetime.now(tz.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=tz.utc)
        else:
            # Convert to UTC for comparison
            v = v.astimezone(tz.utc)

        if v <= now:
            raise ValueError("remind_at phải > now (thời gian hiện tại UTC)")
        return v


class ReminderCreateInternal(ReminderCreate):
    """Internal schema for CRUD operations - includes reminder_id and remind_at_local.

    remind_at_local is calculated from remind_at using user's timezone.
    """

    reminder_id: str
    remind_at_local: datetime


# ============ Update Schemas ============


class ReminderUpdate(BaseModel):
    """Schema for updating a reminder (PATCH request).

    All fields are optional.
    Only provided fields will be updated.
    """

    model_config = ConfigDict(extra="forbid")

    content: Annotated[
        Optional[str],
        Field(
            min_length=1,
            max_length=5000,
            default=None,
            description="Nội dung mới (optional)",
        ),
    ] = None
    title: Annotated[
        Optional[str],
        Field(
            max_length=255,
            default=None,
            description="Tiêu đề mới (optional)",
        ),
    ] = None
    remind_at: Annotated[
        Optional[datetime],
        Field(
            default=None,
            description="Thời gian nhắc nhở mới (optional, phải > now)",
        ),
    ] = None
    reminder_metadata: Annotated[
        Optional[dict],
        Field(
            default=None,
            max_length=10240,
            description="Dữ liệu bổ sung (optional, max 10KB)",
        ),
    ] = None

    @field_validator("remind_at", mode="after")
    @classmethod
    def validate_remind_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate that remind_at is in the future."""
        if v is None:
            return v

        from datetime import timezone as tz

        now = datetime.now(tz.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=tz.utc)

        if v <= now:
            raise ValueError("remind_at phải > now (thời gian hiện tại)")
        return v


class ReminderUpdateInternal(ReminderUpdate):
    """Internal schema for CRUD - includes timestamps for update tracking."""

    status: Optional[ReminderStatus] = None
    received_at: Optional[datetime] = None
    retry_count: Optional[int] = None


# ============ Read Schemas ============


class ReminderRead(BaseModel):
    """Schema for reminder response (detailed view).

    Includes all reminder information.
    """

    id: str
    reminder_id: str
    agent_id: str
    content: str
    title: Optional[str]
    remind_at: datetime
    remind_at_local: datetime
    created_at: datetime
    status: ReminderStatus
    reminder_metadata: Optional[dict]
    received_at: Optional[datetime]
    retry_count: int

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        """Normalize status from model enum to schema enum (uppercase to lowercase)."""
        if hasattr(v, "value"):
            return v.value
        if isinstance(v, str):
            return v.lower()
        return v


class ReminderListRead(BaseModel):
    """Schema for reminder list response (minimal view).

    Includes only essential fields for list display.
    """

    id: str
    reminder_id: str
    agent_id: str
    content: str
    title: Optional[str]
    remind_at: datetime
    remind_at_local: datetime
    created_at: datetime
    status: ReminderStatus

    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v):
        """Normalize status from model enum to schema enum (uppercase to lowercase)."""
        if hasattr(v, "value"):
            return v.value
        if isinstance(v, str):
            return v.lower()
        return v


# ============ Delete Schemas ============


class ReminderDelete(BaseModel):
    """Schema for soft delete operation.

    Used internally for soft delete tracking.
    """

    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
