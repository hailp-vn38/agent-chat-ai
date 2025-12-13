"""
AgentTemplateAssignment model - junction table for agent-template many-to-many relationship.

This model enables templates to be shared across multiple agents.
Each agent can have multiple templates assigned, with one marked as active.
"""

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class AgentTemplateAssignment(Base):
    """Junction table for agent-template many-to-many relationship."""

    __tablename__ = "agent_template_assignment"

    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent.id", ondelete="CASCADE"),
        primary_key=True,
    )

    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("template.id", ondelete="CASCADE"),
        primary_key=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )
