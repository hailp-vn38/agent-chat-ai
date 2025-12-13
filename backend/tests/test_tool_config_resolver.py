"""
Unit tests for ToolConfigResolver.
"""

import pytest
import pytest_asyncio
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.ai.providers.tools.tool_config_resolver import (
    ToolConfigResolver,
    get_tool_names_from_refs,
)
from src.app.models.user import User
from src.app.models.user_tool import UserTool

fake = Faker()


@pytest_asyncio.fixture
async def user_tool_weather(test_user: User, async_session: AsyncSession) -> UserTool:
    """Create a weather user tool config."""
    user_tool = UserTool(
        user_id=str(test_user.id),
        tool_name="get_weather",
        name="My Weather",
        config={"api_key": "user-weather-key", "default_location": "Hanoi"},
        is_active=True,
    )
    async_session.add(user_tool)
    await async_session.commit()
    await async_session.refresh(user_tool)
    return user_tool


@pytest_asyncio.fixture
async def user_tool_music(test_user: User, async_session: AsyncSession) -> UserTool:
    """Create a music user tool config."""
    user_tool = UserTool(
        user_id=str(test_user.id),
        tool_name="play_music",
        name="Home Music",
        config={"music_dir": "/home/user/music"},
        is_active=True,
    )
    async_session.add(user_tool)
    await async_session.commit()
    await async_session.refresh(user_tool)
    return user_tool


class TestToolConfigResolver:
    """Test ToolConfigResolver class."""

    async def test_resolve_system_tool(
        self, async_session: AsyncSession, test_user: User
    ):
        """Test resolving a system tool by name."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={"plugins": {"get_weather": {"default_location": "HCMC"}}},
        )

        result = await resolver.resolve_tools(["get_weather"])

        assert len(result) == 1
        assert result[0]["name"] == "get_weather"
        assert result[0]["source"] == "system"
        assert result[0]["user_tool_id"] is None
        assert result[0]["config"]["default_location"] == "HCMC"

    async def test_resolve_user_tool(
        self,
        async_session: AsyncSession,
        test_user: User,
        user_tool_weather: UserTool,
    ):
        """Test resolving a user tool by UUID."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={},
        )

        result = await resolver.resolve_tools([user_tool_weather.id])

        assert len(result) == 1
        assert result[0]["name"] == "get_weather"
        assert result[0]["source"] == "user"
        assert result[0]["user_tool_id"] == user_tool_weather.id
        assert result[0]["config"]["api_key"] == "user-weather-key"

    async def test_resolve_mixed_tools(
        self,
        async_session: AsyncSession,
        test_user: User,
        user_tool_weather: UserTool,
    ):
        """Test resolving a mix of user and system tools."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={"plugins": {"create_reminder": {}}},
        )

        result = await resolver.resolve_tools(
            [
                user_tool_weather.id,  # User tool
                "create_reminder",  # System tool
            ]
        )

        assert len(result) == 2

        # User tool
        weather = next(t for t in result if t["name"] == "get_weather")
        assert weather["source"] == "user"
        assert weather["user_tool_id"] == user_tool_weather.id

        # System tool
        reminder = next(t for t in result if t["name"] == "create_reminder")
        assert reminder["source"] == "system"
        assert reminder["user_tool_id"] is None

    async def test_user_tool_config_merges_with_base(
        self,
        async_session: AsyncSession,
        test_user: User,
        user_tool_weather: UserTool,
    ):
        """Test that user config merges with base config (user wins)."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={
                "plugins": {
                    "get_weather": {
                        "default_location": "Base Location",
                        "extra_param": "from_base",
                    }
                }
            },
        )

        result = await resolver.resolve_tools([user_tool_weather.id])

        assert len(result) == 1
        config = result[0]["config"]
        # User override wins
        assert config["default_location"] == "Hanoi"
        # Base param is preserved
        assert config["extra_param"] == "from_base"
        # User param exists
        assert config["api_key"] == "user-weather-key"

    async def test_resolve_invalid_uuid(
        self, async_session: AsyncSession, test_user: User
    ):
        """Test resolving an invalid UUID returns nothing."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={},
        )

        result = await resolver.resolve_tools(["00000000-0000-0000-0000-000000000000"])

        assert len(result) == 0

    async def test_resolve_invalid_tool_name(
        self, async_session: AsyncSession, test_user: User
    ):
        """Test resolving an invalid tool name returns nothing."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={},
        )

        result = await resolver.resolve_tools(["nonexistent_tool"])

        assert len(result) == 0

    async def test_resolve_other_user_tool(
        self,
        async_session: AsyncSession,
        test_superuser: User,  # Different user
        user_tool_weather: UserTool,  # Belongs to test_user
    ):
        """Test that other user's tools are not resolved."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_superuser.id),  # Different user
            base_config={},
        )

        result = await resolver.resolve_tools([user_tool_weather.id])

        assert len(result) == 0

    async def test_batch_prefetch(
        self,
        async_session: AsyncSession,
        test_user: User,
        user_tool_weather: UserTool,
        user_tool_music: UserTool,
    ):
        """Test that multiple UUIDs are prefetched in batch."""
        resolver = ToolConfigResolver(
            db=async_session,
            user_id=str(test_user.id),
            base_config={},
        )

        result = await resolver.resolve_tools(
            [
                user_tool_weather.id,
                user_tool_music.id,
            ]
        )

        assert len(result) == 2
        tool_names = [t["name"] for t in result]
        assert "get_weather" in tool_names
        assert "play_music" in tool_names

    async def test_is_uuid_helper(self):
        """Test _is_uuid static method."""
        assert (
            ToolConfigResolver._is_uuid("12345678-1234-1234-1234-123456789012") is True
        )
        assert ToolConfigResolver._is_uuid("get_weather") is False
        assert ToolConfigResolver._is_uuid("short") is False
        assert (
            ToolConfigResolver._is_uuid("12345678123412341234123456789012") is False
        )  # No dashes


class TestGetToolNamesFromRefs:
    """Test get_tool_names_from_refs utility function."""

    def test_with_tool_refs(self):
        """Test with tool refs returns them directly."""
        refs = ["get_weather", "play_music"]
        result = get_tool_names_from_refs(refs)
        assert result == refs

    def test_with_empty_refs_uses_fallback(self):
        """Test empty refs uses fallback."""
        fallback = ["create_reminder", "delete_reminder"]
        result = get_tool_names_from_refs(None, fallback)
        assert result == fallback

    def test_with_none_and_no_fallback(self):
        """Test None refs with no fallback returns empty list."""
        result = get_tool_names_from_refs(None, None)
        assert result == []

    def test_preserves_uuids(self):
        """Test that UUIDs are preserved (not transformed)."""
        refs = ["12345678-1234-1234-1234-123456789012", "get_weather"]
        result = get_tool_names_from_refs(refs)
        assert result == refs
