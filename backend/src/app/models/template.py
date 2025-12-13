"""
Template model - shareable configuration template for agents.

Templates are now independent from agents and can be shared across multiple agents.
The relationship is managed through AgentTemplateAssignment junction table.

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


class Template(Base):
    """Shareable template configuration for agents."""

    __tablename__ = "template"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), index=True)

    # Template config
    name: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(String)

    # Provider references - format: "config:{name}" or "db:{uuid}" or NULL
    # NULL means fallback to selected_module in config.yml
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
    tools: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        insert_default=list,
        default_factory=list,
    )

    summary_memory: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )

    # Sharing flag for future marketplace
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

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
