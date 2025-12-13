"""
Device model - represents an IoT device.

Tracks hardware devices (boards, speakers, microphones) that connect to the server
via WebSocket or MQTT for agent communication.
"""

from datetime import datetime, timezone
from uuid6 import uuid7

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class Device(Base):
    """Device (IoT hardware) model."""

    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint("user_id", "mac_address", name="uq_device_user_mac_address"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mac_address: Mapped[str] = mapped_column(String(50), index=True)

    agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent.id"),
        nullable=True,
        default=None,
        index=True,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    board: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)

    firmware_version: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )

    status: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)

    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
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
