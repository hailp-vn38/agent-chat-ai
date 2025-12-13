"""
Agent model - represents an AI bot agent.

An Agent is a bot instance created by a user that can interact with users
and IoT devices. It can reference a template for configuration and a device for hardware connection.
"""

import secrets
from datetime import datetime, timezone
from uuid6 import uuid7

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Boolean,
    Integer,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base
from ..core.enums import StatusEnum


def _generate_api_key() -> str:
    """Generate a cryptographically secure API key for webhook authentication."""
    return secrets.token_urlsafe(48)


class Agent(Base):
    """Agent (bot AI) model."""

    __tablename__ = "agent"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)

    agent_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String)

    status: Mapped[StatusEnum] = mapped_column(
        ENUM(StatusEnum, name="status", native_enum=True), default=StatusEnum.disabled
    )

    active_template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("template.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    device_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("device.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    device_mac_address: Mapped[str | None] = mapped_column(
        String(17), nullable=True, default=None, index=True
    )

    user_profile: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )

    # Chat history config: 0=disabled, 1=text only, 2=text+audio
    chat_history_conf: Mapped[int] = mapped_column(Integer, default=1)

    api_key: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        index=True,
        default=None,
        nullable=True,
        comment="Unique API key for webhook authentication (generated on demand)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        init=False,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
