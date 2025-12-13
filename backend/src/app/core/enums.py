"""
Enumeration types for core data models.

Provides type-safe enums for Agent status and Chat message types.
"""

from enum import Enum


class StatusEnum(str, Enum):
    """Agent status enumeration."""

    disabled = "disabled"
    enabled = "enabled"


class ChatTypeEnum(str, Enum):
    """Chat message type enumeration."""

    user = "user"
    agent = "agent"
