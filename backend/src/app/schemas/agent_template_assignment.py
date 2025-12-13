"""
AgentTemplateAssignment schemas - Pydantic models for junction table operations.

Manages the many-to-many relationship between agents and templates.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AssignmentBase(BaseModel):
    """Base assignment schema."""

    agent_id: str
    template_id: str


class AssignmentCreate(AssignmentBase):
    """Schema for creating a new assignment."""

    is_active: bool = Field(default=False)


class AssignmentRead(AssignmentBase):
    """Schema for reading assignment."""

    is_active: bool
    assigned_at: datetime


class AssignmentWithTemplateRead(BaseModel):
    """Schema for reading assignment with template details."""

    agent_id: str
    template_id: str
    is_active: bool
    assigned_at: datetime
    template_name: str | None = None
