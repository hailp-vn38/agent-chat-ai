"""
AgentMessage schemas - Pydantic models for chat message validation and serialization.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AgentMessageBase(BaseModel):
    """Base schema for agent message."""

    agent_id: str
    session_id: str
    chat_type: Annotated[int, Field(ge=1, le=2, description="1=user, 2=assistant")]
    content: str


class AgentMessageCreate(AgentMessageBase):
    """Schema for creating a new message."""

    model_config = ConfigDict(extra="forbid")


class AgentMessageRead(AgentMessageBase):
    """Schema for reading message data."""

    id: str
    created_at: datetime


class SessionSummary(BaseModel):
    """Schema for session summary in list."""

    session_id: str
    first_message_at: datetime
    last_message_at: datetime
    message_count: int


class AgentMessageDelete(BaseModel):
    """Schema for delete response."""

    deleted_count: int

