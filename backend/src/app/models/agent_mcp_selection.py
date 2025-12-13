"""
Agent MCP Selection models - Normalized storage for MCP server selections per agent.

Models:
- AgentMCPSelection: Tracks MCP selection mode per agent
- AgentMCPServerSelected: Stores selected MCP servers with resolved metadata
"""

from datetime import datetime, timezone
from uuid6 import uuid7

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class AgentMCPSelection(Base):
    """Track MCP selection configuration per agent.

    One-to-one relationship with Agent.
    Stores the selection mode ('all' or 'selected') and references to AgentMCPServerSelected records.
    """

    __tablename__ = "agent_mcp_selection"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    mcp_selection_mode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="all",
        comment="MCP selection mode: 'all' (use all available MCPs) or 'selected' (use only selected MCPs)",
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


class AgentMCPServerSelected(Base):
    """Store selected MCP servers with resolved metadata per agent selection.

    Many-to-one relationship with AgentMCPSelection.
    Each record represents one MCP server in an agent's selection with its resolved metadata.
    Metadata (name, type, description) is resolved at selection time and stored here.
    """

    __tablename__ = "agent_mcp_server_selected"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    agent_mcp_selection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_mcp_selection.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="MCP server reference: 'db:{uuid}' (user-defined) or 'config:{name}' (system config)",
    )

    mcp_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Resolved MCP server name from reference",
    )

    mcp_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="MCP transport type: 'stdio', 'sse', or 'http'",
    )

    source: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="MCP server source: 'user' (from server_mcp_config) or 'config' (from config.yml)",
    )

    mcp_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="MCP server description",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this MCP server is active/available",
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when MCP metadata was last resolved from source",
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

    # Ensure no duplicate MCP references per selection
    __table_args__ = (
        UniqueConstraint(
            "agent_mcp_selection_id",
            "reference",
            name="uq_agent_mcp_selection_reference",
        ),
    )
