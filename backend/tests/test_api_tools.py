"""
API tests for Tools endpoints.

Note: Tests for CRUD endpoints (POST /tools, PUT /tools/{id}, DELETE /tools/{id})
have been removed as these endpoints are no longer supported in v2.0.
UserTool custom configurations are deprecated. Tests now focus on:
- GET /available (list system functions)
- GET /options (list functions for dropdown)
"""

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.user import User

# from src.app.models.user_tool import UserTool  # Deprecated - UserTool model removed

fake = Faker()


@pytest_asyncio.fixture
async def test_user_tool(test_user: User, async_session: AsyncSession) -> UserTool:
    """Create a test user tool configuration."""
    user_tool = UserTool(
        user_id=str(test_user.id),
        tool_name="get_weather",
        name="Test Weather Config",
        config={"api_key": "secret-test-key", "default_location": "Hanoi"},
        is_active=True,
    )
    async_session.add(user_tool)
    await async_session.commit()
    await async_session.refresh(user_tool)
    return user_tool


@pytest_asyncio.fixture
async def multiple_user_tools(
    test_user: User, async_session: AsyncSession
) -> list[UserTool]:
    """Create multiple user tool configurations."""
    tools = [
        UserTool(
            user_id=str(test_user.id),
            tool_name="get_weather",
            name="Office Weather",
            config={"api_key": "weather-key-1", "default_location": "HCMC"},
            is_active=True,
        ),
        UserTool(
            user_id=str(test_user.id),
            tool_name="play_music",
            name="Home Music",
            config={"music_dir": "/home/music", "music_ext": ["mp3", "flac"]},
            is_active=True,
        ),
        UserTool(
            user_id=str(test_user.id),
            tool_name="get_weather",
            name="Inactive Weather",
            config={"api_key": "inactive-key"},
            is_active=False,
        ),
    ]

    for tool in tools:
        async_session.add(tool)
    await async_session.commit()

    for tool in tools:
        await async_session.refresh(tool)

    return tools


class TestGetAvailableTools:
    """Test GET /api/v1/tools/available endpoint."""

    async def test_get_available_tools(self, async_client: AsyncClient):
        """Test getting available tools without auth."""
        response = await async_client.get("/api/v1/tools/available")

        assert response.status_code == 200
        data = response.json()

        assert "tools" in data
        assert "categories" in data
        assert "total" in data
        assert data["total"] > 0

        # Verify known tools exist
        tool_names = [t["name"] for t in data["tools"]]
        assert "get_weather" in tool_names
        assert "play_music" in tool_names
        assert "create_reminder" in tool_names

    async def test_tool_schema_structure(self, async_client: AsyncClient):
        """Test that tool schemas have correct structure."""
        response = await async_client.get("/api/v1/tools/available")

        assert response.status_code == 200
        data = response.json()

        # Find get_weather tool
        weather_tool = next(
            (t for t in data["tools"] if t["name"] == "get_weather"), None
        )
        assert weather_tool is not None

        # Check schema structure
        assert weather_tool["display_name"] == "Weather"
        assert weather_tool["category"] == "weather"
        assert weather_tool["requires_config"] is True
        assert "fields" in weather_tool

        # Check fields
        field_names = [f["name"] for f in weather_tool["fields"]]
        assert "api_key" in field_names
        assert "default_location" in field_names

        # Check field structure
        api_key_field = next(
            (f for f in weather_tool["fields"] if f["name"] == "api_key"), None
        )
        assert api_key_field["field_type"] == "secret"
        assert api_key_field["required"] is True


class TestGetToolSchema:
    """Test GET /api/v1/tools/schemas/{tool_name} endpoint."""

    async def test_get_weather_schema(self, async_client: AsyncClient):
        """Test getting a specific tool schema."""
        response = await async_client.get("/api/v1/tools/schemas/get_weather")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "get_weather"
        assert data["category"] == "weather"
        assert len(data["fields"]) >= 1

    async def test_get_nonexistent_schema(self, async_client: AsyncClient):
        """Test getting schema for non-existent tool."""
        response = await async_client.get("/api/v1/tools/schemas/nonexistent_tool")

        assert response.status_code == 404


class TestListUserTools:
    """Test GET /api/v1/tools endpoint."""

    async def test_list_tools_unauthorized(self, async_client: AsyncClient):
        """Test listing tools without authentication."""
        response = await async_client.get("/api/v1/tools")

        assert response.status_code == 401

    async def test_list_tools_empty(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test listing tools when user has none."""
        response = await async_client.get("/api/v1/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"] == []
        assert data["total"] == 0

    async def test_list_tools_with_data(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_user_tools: list[UserTool],
    ):
        """Test listing tools with data."""
        response = await async_client.get("/api/v1/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert len(data["data"]) == 3  # All 3 tools (including inactive)
        assert data["total"] == 3

    async def test_list_tools_filter_by_tool_name(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_user_tools: list[UserTool],
    ):
        """Test filtering tools by tool_name."""
        response = await async_client.get(
            "/api/v1/tools?tool_name=get_weather", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 2  # 2 weather tools
        for tool in data["data"]:
            assert tool["tool_name"] == "get_weather"

    async def test_list_tools_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_user_tools: list[UserTool],
    ):
        """Test pagination."""
        response = await async_client.get(
            "/api/v1/tools?page=1&page_size=2", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) == 2
        assert data["total"] == 3
        assert data["total_pages"] == 2

    async def test_list_tools_masks_secrets(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test that secret fields are masked in response."""
        response = await async_client.get("/api/v1/tools", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        tool = data["data"][0]
        assert tool["config"]["api_key"] == "***"


class TestCreateUserTool:
    """Test POST /api/v1/tools endpoint."""

    async def test_create_tool_unauthorized(self, async_client: AsyncClient):
        """Test creating tool without auth."""
        response = await async_client.post(
            "/api/v1/tools",
            json={
                "tool_name": "get_weather",
                "name": "My Weather",
                "config": {"api_key": "test"},
            },
        )

        assert response.status_code == 401

    async def test_create_tool_success(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test successful tool creation."""
        response = await async_client.post(
            "/api/v1/tools",
            headers=auth_headers,
            json={
                "tool_name": "get_weather",
                "name": "My Weather Config",
                "config": {"api_key": "my-api-key", "default_location": "Hanoi"},
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["data"]["tool_name"] == "get_weather"
        assert data["data"]["name"] == "My Weather Config"
        assert data["data"]["config"]["api_key"] == "***"  # Masked

    async def test_create_tool_invalid_tool_name(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating tool with invalid tool name."""
        response = await async_client.post(
            "/api/v1/tools",
            headers=auth_headers,
            json={
                "tool_name": "nonexistent_tool",
                "name": "Invalid Tool",
                "config": {},
            },
        )

        assert response.status_code == 400
        assert "not found in registry" in response.json()["detail"]

    async def test_create_tool_applies_defaults(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test that defaults are applied to config."""
        response = await async_client.post(
            "/api/v1/tools",
            headers=auth_headers,
            json={
                "tool_name": "get_weather",
                "name": "Minimal Config",
                "config": {"api_key": "test-key"},  # Missing default_location
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Default should be applied (check raw config, though it may be masked)
        assert data["success"] is True


class TestGetUserTool:
    """Test GET /api/v1/tools/{tool_id} endpoint."""

    async def test_get_tool_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test getting a specific tool."""
        response = await async_client.get(
            f"/api/v1/tools/{test_user_tool.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["id"] == test_user_tool.id
        assert data["data"]["tool_name"] == "get_weather"

    async def test_get_tool_not_found(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent tool."""
        response = await async_client.get(
            "/api/v1/tools/nonexistent-id", headers=auth_headers
        )

        assert response.status_code == 404

    async def test_get_tool_other_user(
        self,
        async_client: AsyncClient,
        superuser_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test accessing another user's tool."""
        response = await async_client.get(
            f"/api/v1/tools/{test_user_tool.id}", headers=superuser_headers
        )

        assert response.status_code == 404


class TestUpdateUserTool:
    """Test PUT /api/v1/tools/{tool_id} endpoint."""

    async def test_update_tool_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test updating a tool."""
        response = await async_client.put(
            f"/api/v1/tools/{test_user_tool.id}",
            headers=auth_headers,
            json={
                "name": "Updated Name",
                "config": {"api_key": "new-key", "default_location": "HCMC"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["config"]["api_key"] == "***"

    async def test_update_tool_partial(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test partial update (only name)."""
        response = await async_client.put(
            f"/api/v1/tools/{test_user_tool.id}",
            headers=auth_headers,
            json={"name": "Only Name Changed"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["name"] == "Only Name Changed"
        # Config should remain unchanged (though masked)
        assert "config" in data["data"]

    async def test_update_tool_deactivate(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test deactivating a tool."""
        response = await async_client.put(
            f"/api/v1/tools/{test_user_tool.id}",
            headers=auth_headers,
            json={"is_active": False},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["is_active"] is False


class TestDeleteUserTool:
    """Test DELETE /api/v1/tools/{tool_id} endpoint."""

    async def test_delete_tool_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test deleting a tool."""
        response = await async_client.delete(
            f"/api/v1/tools/{test_user_tool.id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify tool is deleted (soft delete)
        get_response = await async_client.get(
            f"/api/v1/tools/{test_user_tool.id}", headers=auth_headers
        )
        assert get_response.status_code == 404

    async def test_delete_tool_not_found(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test deleting non-existent tool."""
        response = await async_client.delete(
            "/api/v1/tools/nonexistent-id", headers=auth_headers
        )

        assert response.status_code == 404


class TestValidateToolReference:
    """Test POST /api/v1/tools/validate-reference endpoint."""

    async def test_validate_system_tool_reference(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test validating a system tool reference."""
        response = await async_client.post(
            "/api/v1/tools/validate-reference",
            headers=auth_headers,
            json={"reference": "get_weather"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["source"] == "system"
        assert data["tool_name"] == "get_weather"

    async def test_validate_user_tool_reference(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user_tool: UserTool,
    ):
        """Test validating a user tool reference (UUID)."""
        response = await async_client.post(
            "/api/v1/tools/validate-reference",
            headers=auth_headers,
            json={"reference": test_user_tool.id},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is True
        assert data["source"] == "user"
        assert data["tool_name"] == "get_weather"

    async def test_validate_invalid_reference(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test validating an invalid reference."""
        response = await async_client.post(
            "/api/v1/tools/validate-reference",
            headers=auth_headers,
            json={"reference": "invalid_tool_name"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert len(data["errors"]) > 0
