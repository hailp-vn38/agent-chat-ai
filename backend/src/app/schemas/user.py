from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..core.schemas import PersistentDeletion, TimestampSchema


class UserBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=30, examples=["User Userson"])]
    email: Annotated[EmailStr, Field(examples=["user.userson@example.com"])]


class User(TimestampSchema, UserBase, PersistentDeletion):
    id: str
    profile_image_base64: Annotated[str | None, Field(default=None)]
    hashed_password: str
    is_superuser: bool = False


class UserRead(BaseModel):
    id: str

    name: Annotated[str, Field(min_length=2, max_length=30, examples=["User Userson"])]
    email: Annotated[EmailStr, Field(examples=["user.userson@example.com"])]
    profile_image_base64: str | None = None


class UserCreate(UserBase):
    model_config = ConfigDict(extra="forbid")

    password: Annotated[
        str,
        Field(
            pattern=r"^.{8,}|[0-9]+|[A-Z]+|[a-z]+|[^a-zA-Z0-9]+$",
            examples=["Str1ngst!"],
        ),
    ]


class UserCreateInternal(UserBase):
    hashed_password: str


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str | None,
        Field(min_length=2, max_length=30, examples=["User Userberg"], default=None),
    ]
    email: Annotated[
        EmailStr | None, Field(examples=["user.userberg@example.com"], default=None)
    ]
    profile_image_base64: Annotated[
        str | None,
        Field(
            description="Base64 encoded image data (e.g., 'data:image/png;base64,iVBOR...')",
            default=None,
        ),
    ]
    timezone: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=50,
            examples=["Asia/Ho_Chi_Minh", "UTC", "America/New_York"],
            default=None,
        ),
    ]


class UserUpdateInternal(UserUpdate):
    updated_at: datetime


class UserDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_deleted: bool
    deleted_at: datetime


class UserRestoreDeleted(BaseModel):
    is_deleted: bool


class PasswordChange(BaseModel):
    """Schema for changing user password."""

    model_config = ConfigDict(extra="forbid")

    current_password: Annotated[str, Field(min_length=1, examples=["OldPassword123!"])]
    new_password: Annotated[
        str,
        Field(
            pattern=r"^.{8,}|[0-9]+|[A-Z]+|[a-z]+|[^a-zA-Z0-9]+$",
            examples=["NewPassword123!"],
            description="Must be at least 8 characters with uppercase, lowercase, number, and special character",
        ),
    ]
