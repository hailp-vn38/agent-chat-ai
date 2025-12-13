"""
AgentMessage model - stores chat messages for agent sessions.

Messages are linked to agents via FK with CASCADE delete.
Each message belongs to a session (grouped by session_id).
"""

from datetime import datetime, timezone

from uuid6 import uuid7

from sqlalchemy import DateTime, ForeignKey, String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class AgentMessage(Base):
    """Agent chat message model."""

    __tablename__ = "agent_message"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent.id", ondelete="CASCADE"),
        index=True,
    )

    session_id: Mapped[str] = mapped_column(String(36), index=True)

    # 1 = user, 2 = assistant
    chat_type: Mapped[int] = mapped_column(Integer)

    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )
