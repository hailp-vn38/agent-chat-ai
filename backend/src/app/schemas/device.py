"""
Device schemas - Pydantic models for validation and serialization.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    """Base device schema."""

    user_id: str
    mac_address: Annotated[
        str, Field(min_length=1, max_length=50, examples=["00:1A:2B:3C:4D:5E"])
    ]
    device_name: str | None = Field(default=None, max_length=255)
    board: str | None = Field(
        default=None, max_length=100, examples=["ESP32", "Raspberry Pi"]
    )
    firmware_version: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)


class DeviceCreate(DeviceBase):
    """Schema for creating a new device."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str | None = None
    user_id: str  # Auto-populated from current user in API, but required in schema


class DeviceRead(DeviceBase):
    """Schema for reading device data."""

    id: str
    user_id: str
    agent_id: str | None = None
    last_connected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DeviceUpdate(BaseModel):
    """Schema for updating device."""

    model_config = ConfigDict(extra="forbid")

    device_name: str | None = Field(default=None, max_length=255)
    board: str | None = Field(default=None, max_length=100)
    firmware_version: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)
    agent_id: str | None = None
    last_connected_at: datetime | None = None
    user_id: str | None = None


class DeviceUpdateInternal(DeviceUpdate):
    """Internal schema for updating device (includes timestamp)."""

    updated_at: datetime
