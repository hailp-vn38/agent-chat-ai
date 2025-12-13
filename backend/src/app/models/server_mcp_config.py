"""
ServerMCPConfig model - represents user-scoped MCP server configuration.

Each user can define multiple MCP servers with custom settings and configurations.
Supports stdio (command-based) and SSE/HTTP (network-based) transports.
"""

from datetime import datetime, timezone
from uuid6 import uuid7

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Boolean,
    JSON,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class ServerMCPConfig(Base):
    """User-scoped MCP server configuration model."""

    __tablename__ = "server_mcp_config"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Description - optional
    description: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    # Stdio-specific configs
    command: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    args: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    env: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    # SSE/HTTP-specific configs
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True, default=None)
    headers: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)

    # Tools metadata
    tools: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    tools_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Configuration state
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

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_mcp_name"),
        CheckConstraint(
            "(type = 'stdio' AND command IS NOT NULL) OR "
            "(type IN ('sse', 'http') AND url IS NOT NULL)",
            name="ck_mcp_config_required_fields",
        ),
        CheckConstraint(
            "type IN ('stdio', 'sse', 'http')",
            name="ck_mcp_config_type",
        ),
    )
