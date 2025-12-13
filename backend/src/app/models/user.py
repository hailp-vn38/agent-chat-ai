from uuid6 import uuid7
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default_factory=lambda: str(uuid7()), init=False
    )

    name: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

    profile_image_base64: Mapped[str | None] = mapped_column(
        Text, default=None, nullable=True, comment="Base64 encoded profile image"
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        default="UTC",
        nullable=False,
        index=True,
        comment="User's canonical timezone (e.g., 'Asia/Ho_Chi_Minh')",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
