"""
Provider model - User-defined AI provider configurations.

Stores LLM, TTS, ASR provider configs with validated JSON schema.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from ..core.db.database import Base


class Provider(Base):
    """User-defined provider configuration."""

    __tablename__ = "provider"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id"), index=True
    )

    name: Mapped[str] = mapped_column(String(255))

    category: Mapped[str] = mapped_column(
        String(50), index=True
    )  # LLM, TTS, ASR, VAD, Memory, Intent

    type: Mapped[str] = mapped_column(String(50))  # openai, gemini, edge, google, ...

    config: Mapped[dict] = mapped_column(JSON)  # Validated provider config

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

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

