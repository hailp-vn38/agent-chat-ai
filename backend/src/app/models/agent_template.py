"""
AgentTemplate model - configuration template for an agent.

Stores AI model references, prompts, and configuration settings
used by an agent to process and respond to messages.

Provider fields (ASR, LLM, VLLM, TTS, Memory, Intent) store provider references:
- "config:{name}" - Provider from config.yml (e.g., "config:CopilotLLM")
- "db:{uuid}" - Provider from database (e.g., "db:019abc-def...")
- NULL - Fallback to selected_module in config.yml

Tools field stores tool references:
- List of strings: UserTool UUIDs or system tool names
- Empty list/NULL - Fallback to config["Intent"]["functions"]
"""

from datetime import datetime, timezone
from uuid6 import uuid7

from sqlalchemy import DateTime, ForeignKey, String, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class AgentTemplate(Base):
    """Agent template (configuration) model."""

    __tablename__ = "agent_template"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent.id", ondelete="CASCADE"), index=True
    )

    agent_name: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Provider references - format: "config:{name}" or "db:{uuid}" or NULL
    # NULL means fallback to selected_module in config.yml
    # NOTE: Removed FK constraints to support config:{name} format
    ASR: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    LLM: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    VLLM: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    TTS: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    Memory: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    Intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        index=True,
    )

    # Tool references - list of UserTool UUIDs or system tool names
    # Empty list/NULL means fallback to config["Intent"]["functions"]
    tools: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        insert_default=list,
        default_factory=list,
    )

    summary_memory: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
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
