"""Reminder model - Quản lý nhắc nhở với đầy đủ trạng thái và lịch sử.

Pattern: SQLAlchemy 2.0 with Mapped type annotations, no relationships.
Soft delete support: is_deleted field for data preservation.
Status tracking: pending → delivered → received (or failed)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Integer,
    Boolean,
    Text,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from ..core.db.database import Base
from ..core.logger import get_logger

logger = get_logger(__name__)


class ReminderStatus(str, Enum):
    """Trạng thái của nhắc nhở."""

    PENDING = "pending"  # Chờ lên lịch
    DELIVERED = "delivered"  # Đã gửi MQTT tới thiết bị
    RECEIVED = "received"  # Thiết bị đã nhận và xử lý
    FAILED = "failed"  # Gửi thất bại


class Reminder(Base):
    """Reminder model for managing reminders with full state tracking.

    Attributes:
        id: Unique identifier (UUID)
        reminder_id: String identifier từ scheduler (unique, dùng để lookup nhanh)
        agent_id: Foreign key to agent table (canonical agent ownership)
        content: Nội dung nhắc nhở (bắt buộc)
        title: Tiêu đề nhắc nhở (optional)
        remind_at: Thời gian nhắc nhở (UTC, server time)
        remind_at_local: Thời gian nhắc nhở theo timezone của user
        created_at: Thời gian tạo nhắc nhở
        status: Trạng thái nhắc nhở (pending/delivered/received/failed)
        metadata: Dữ liệu bổ sung (JSON)
        received_at: Thời gian thiết bị nhận và xử lý (optional)
        retry_count: Số lần thử lại gửi MQTT
        is_deleted: Soft delete flag
    """

    __tablename__ = "reminder"

    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    # Unique identifier từ scheduler
    reminder_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Identifier từ scheduler (dùng để lookup nhanh)",
    )

    # Foreign Keys - Required
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Liên kết với agent (canonical ownership)",
    )

    # Content fields - Required (no defaults)
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Nội dung nhắc nhở (1-5000 ký tự)",
    )

    # Datetime fields - Required (no defaults)
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Thời gian nhắc nhở (UTC)",
    )

    remind_at_local: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Thời gian nhắc nhở (timezone địa phương)",
    )

    # Fields with defaults (must come after required fields)
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Tiêu đề nhắc nhở (max 255 ký tự)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="Thời gian tạo nhắc nhở",
    )

    # Status tracking with default
    status: Mapped[ReminderStatus] = mapped_column(
        SQLEnum(ReminderStatus),
        default=ReminderStatus.PENDING,
        nullable=False,
        index=True,
        comment="Trạng thái nhắc nhở",
    )

    # Optional tracking datetimes
    received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Thời gian thiết bị nhận và xử lý",
    )

    # Additional fields with defaults
    reminder_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Dữ liệu bổ sung (< 10KB)",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Số lần thử lại gửi MQTT",
    )

    # Soft Delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Soft delete flag - set to True thay vì hard delete",
    )

    def __repr__(self) -> str:
        """String representation of Reminder."""
        return (
            f"<Reminder("
            f"id={self.id}, "
            f"reminder_id={self.reminder_id}, "
            f"device_id={self.device_id}, "
            f"status={self.status}, "
            f"remind_at={self.remind_at}"
            f")>"
        )
