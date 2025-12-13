"""
Comprehensive test suite for Agent API endpoints.

Tests cover:
- Agent CRUD operations (list, get, create, update, delete)
- Template assignment/unassignment endpoints
- Device binding/unbinding operations
- Authentication and authorization
- Pagination and error scenarios
- Test isolation and data cleanup
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import StatusEnum
from src.app.models.agent import Agent
from src.app.models.template import Template
from src.app.models.agent_template_assignment import AgentTemplateAssignment
from src.app.models.device import Device
from src.app.models.user import User


# ========== Agent CRUD Endpoint Tests ==========


class TestAgentList:
    """Tests for GET /agents - list agents with pagination."""

    @pytest.mark.asyncio
    async def test_list_agents_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_agent: Agent,
        clean_database,
    ):
        """Should return paginated list of user's agents."""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] >= 1
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert len(data["data"]) >= 1
        assert data["data"][0]["agent_name"] == test_agent.agent_name

    @pytest.mark.asyncio
    async def test_list_agents_unauthenticated(
        self,
        async_client: AsyncClient,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.get("/api/v1/agents")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_agents_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_agents: list[Agent],
        clean_database,
    ):
        """Should handle pagination correctly."""
        # Get first page with 2 items
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
            params={"page": 1, "page_size": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        # Should have 4 active agents (one is soft-deleted)
        assert data["total"] == 4

    @pytest.mark.asyncio
    async def test_list_agents_filters_soft_deleted(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_agents: list[Agent],
        clean_database,
    ):
        """Should not return soft-deleted agents."""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should only return 4 active agents (5th is soft-deleted)
        assert data["total"] == 4
        for agent in data["data"]:
            assert agent["agent_name"] != "Agent 4"


class TestAgentGet:
    """Tests for GET /agents/{agent_id} - get agent detail."""

    @pytest.mark.asyncio
    async def test_get_agent_detail_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return agent detail for owned agent."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent"]["id"] == str(test_agent.id)
        assert data["agent"]["agent_name"] == test_agent.agent_name
        assert "templates" in data
        assert "device" in data

    @pytest.mark.asyncio
    async def test_get_agent_with_device(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_device: Agent,
        clean_database,
    ):
        """Should include device info when agent has bound device."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent_with_device.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["device"] is not None
        assert data["device"]["id"] == str(test_agent_with_device.device_id)

    @pytest.mark.asyncio
    async def test_get_agent_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        # Create agent for superuser
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            description="Other agent description",
            status=StatusEnum.enabled,
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.get(
            f"/api/v1/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.get(f"/api/v1/agents/{test_agent.id}")
        assert response.status_code == 401


class TestAgentCreate:
    """Tests for POST /agents - create agent."""

    @pytest.mark.asyncio
    async def test_create_agent_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should create agent with valid data."""
        agent_data = {
            "agent_name": "New Test Agent",
            "description": "Test description",
            "status": "enabled",
        }

        response = await async_client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json=agent_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["agent_name"] == agent_data["agent_name"]
        assert data["description"] == agent_data["description"]
        assert data["status"] == agent_data["status"]
        assert "id" in data
        assert "user_id" in data

    @pytest.mark.asyncio
    async def test_create_agent_duplicate_name(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 400 when agent name already exists."""
        agent_data = {
            "agent_name": test_agent.agent_name,
            "description": "Test description",
            "status": "enabled",
        }

        response = await async_client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json=agent_data,
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_agent_unauthenticated(
        self,
        async_client: AsyncClient,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        agent_data = {
            "agent_name": "New Test Agent",
            "description": "Test description",
        }

        response = await async_client.post("/api/v1/agents", json=agent_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_agent_invalid_data(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return 422 for invalid data."""
        agent_data = {
            "agent_name": "",  # Empty name
            "description": "Test",
        }

        response = await async_client.post(
            "/api/v1/agents",
            headers=auth_headers,
            json=agent_data,
        )

        assert response.status_code == 422


class TestAgentUpdate:
    """Tests for PUT /agents/{agent_id} - update agent."""

    @pytest.mark.asyncio
    async def test_update_agent_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should update agent with valid data."""
        update_data = {
            "agent_name": "Updated Agent Name",
            "description": "Updated description",
        }

        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == update_data["agent_name"]
        assert data["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_update_agent_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            description="Other agent description",
            status=StatusEnum.enabled,
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        update_data = {"agent_name": "Hacked Name"}

        response = await async_client.put(
            f"/api/v1/agents/{other_agent.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_agent_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        update_data = {"agent_name": "Updated Name"}

        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}",
            json=update_data,
        )

        assert response.status_code == 401


class TestAgentDelete:
    """Tests for DELETE /agents/{agent_id} - delete agent."""

    @pytest.mark.asyncio
    async def test_delete_agent_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should delete agent successfully."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify agent is deleted
        get_response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent_with_device_cascades(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_device: Agent,
        clean_database,
    ):
        """Should delete agent and cascade to device."""
        device_id = test_agent_with_device.device_id

        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_device.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_agent_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            description="Other agent description",
            status=StatusEnum.enabled,
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.delete(
            f"/api/v1/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_agent_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.delete(f"/api/v1/agents/{test_agent.id}")
        assert response.status_code == 401


# ========== Template Assignment Endpoint Tests ==========


class TestAgentTemplatesAssignment:
    """Tests for POST/DELETE /agents/{agent_id}/templates/{template_id} - assign/unassign templates."""

    @pytest.mark.asyncio
    async def test_assign_template_to_agent_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_template: Template,
        clean_database,
    ):
        """Should assign template to agent successfully."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/templates/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["agent_id"] == str(test_agent.id)
        assert data["data"]["template_id"] == str(test_template.id)

    @pytest.mark.asyncio
    async def test_assign_template_set_active(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_template: Template,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should set template as active when set_active=True."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/templates/{test_template.id}",
            headers=auth_headers,
            params={"set_active": True},
        )

        assert response.status_code == 201

        # Verify agent's active_template_id is set
        await async_session.refresh(test_agent)
        assert str(test_agent.active_template_id) == str(test_template.id)

    @pytest.mark.asyncio
    async def test_assign_public_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_public_template: Template,
        clean_database,
    ):
        """Should allow assigning public template from other user."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/templates/{test_public_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_assign_private_template_from_other_user(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 403 for private template from other user."""
        other_template = Template(
            name="Other Template",
            user_id=str(test_superuser.id),
            prompt="Test prompt",
            is_public=False,
        )
        async_session.add(other_template)
        await async_session.commit()
        await async_session.refresh(other_template)

        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/templates/{other_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_template_not_owned_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            status=StatusEnum.enabled,
            description="Other agent description",
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.post(
            f"/api/v1/agents/{other_agent.id}/templates/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/templates/{test_template.id}",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unassign_template_from_agent_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_assignment: tuple[Agent, Template, AgentTemplateAssignment],
        clean_database,
    ):
        """Should unassign template from agent successfully."""
        agent, template, assignment = test_agent_with_assignment

        response = await async_client.delete(
            f"/api/v1/agents/{agent.id}/templates/{template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_unassign_active_template_clears(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_template: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should clear active_template_id when unassigning active template."""
        template_id = test_agent_with_template.active_template_id

        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_template.id}/templates/{template_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify active_template_id is cleared
        await async_session.refresh(test_agent_with_template)
        assert test_agent_with_template.active_template_id is None

    @pytest.mark.asyncio
    async def test_unassign_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_template: Template,
        clean_database,
    ):
        """Should return 404 when assignment doesn't exist."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}/templates/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unassign_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}/templates/{test_template.id}",
        )
        assert response.status_code == 401


class TestListAgentTemplates:
    """Tests for GET /agents/{agent_id}/templates - list assigned templates."""

    @pytest.mark.asyncio
    async def test_list_agent_templates_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_template: Agent,
        clean_database,
    ):
        """Should return list of templates assigned to agent."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent_with_template.id}/templates",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_agent_templates_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return empty list when no templates assigned."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/templates",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_agent_templates_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            status=StatusEnum.enabled,
            description="Other agent description",
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.get(
            f"/api/v1/agents/{other_agent.id}/templates",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_agent_templates_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/templates",
        )
        assert response.status_code == 401


class TestActivateTemplate:
    """Tests for PUT /agents/{agent_id}/activate-template/{template_id}."""

    @pytest.mark.asyncio
    async def test_activate_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_assignment: tuple[Agent, Template, AgentTemplateAssignment],
        async_session: AsyncSession,
        clean_database,
    ):
        """Should activate assigned template."""
        agent, template, assignment = test_agent_with_assignment

        response = await async_client.put(
            f"/api/v1/agents/{agent.id}/activate-template/{template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["active_template_id"] == str(template.id)

    @pytest.mark.asyncio
    async def test_activate_template_auto_assigns(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_template: Template,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should auto-assign template if not already assigned and then activate."""
        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}/activate-template/{test_template.id}",
            headers=auth_headers,
        )

        # Should succeed (auto-assign then activate)
        assert response.status_code == 200
        data = response.json()
        assert data["active_template_id"] == str(test_template.id)

        # Verify agent's active_template_id is set
        await async_session.refresh(test_agent)
        assert str(test_agent.active_template_id) == str(test_template.id)

    @pytest.mark.asyncio
    async def test_activate_template_not_owned_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            status=StatusEnum.enabled,
            description="Other agent description",
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.put(
            f"/api/v1/agents/{other_agent.id}/activate-template/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_activate_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}/activate-template/{test_template.id}",
        )
        assert response.status_code == 401


# ========== Device Binding Endpoint Tests ==========


class TestBindDevice:
    """Tests for POST /agents/{agent_id}/bind-device - bind device to agent."""

    @pytest.mark.asyncio
    async def test_bind_device_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_user: User,
        clean_database,
    ):
        """Should bind device with valid activation code."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        # Mock cache manager
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            side_effect=[
                "AA:BB:CC:DD:EE:FF",  # mac_address from activation code
                {  # device data
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_name": "Test Device",
                    "board": "ESP32",
                    "firmware_version": "1.0.0",
                },
            ]
        )
        mock_cache.delete = AsyncMock()

        # Override dependency
        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["mac_address"] == "AA:BB:CC:DD:EE:FF"
            assert data["device_name"] == "Test Device"
            assert "id" in data
        finally:
            # Clean up override
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_creates_with_user_id(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_user: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should create device with user_id."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            side_effect=[
                "AA:BB:CC:DD:EE:FF",
                {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_name": "Test Device",
                    "board": "ESP32",
                    "firmware_version": "1.0.0",
                },
            ]
        )
        mock_cache.delete = AsyncMock()

        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 200
            device_id = response.json()["id"]

            # Verify device has user_id
            from src.app.crud.crud_device import crud_device
            from src.app.schemas.device import DeviceRead

            device = await crud_device.get(
                db=async_session,
                id=device_id,
                schema_to_select=DeviceRead,
                return_as_model=True,
            )
            assert device.user_id == str(test_user.id)
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_updates_agent_device_id(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should update agent device_id after binding."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            side_effect=[
                "AA:BB:CC:DD:EE:FF",
                {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_name": "Test Device",
                    "board": "ESP32",
                    "firmware_version": "1.0.0",
                },
            ]
        )
        mock_cache.delete = AsyncMock()

        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 200
            device_id = response.json()["id"]

            # Verify agent device_id updated
            await async_session.refresh(test_agent)
            assert test_agent.device_id == device_id
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_clears_cache(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should clear cache after binding."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            side_effect=[
                "AA:BB:CC:DD:EE:FF",
                {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "device_name": "Test Device",
                    "board": "ESP32",
                    "firmware_version": "1.0.0",
                },
            ]
        )
        mock_cache.delete = AsyncMock()

        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 200
            # Verify cache.delete was called twice
            assert mock_cache.delete.call_count == 2
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_invalid_activation_code(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 400 for invalid activation code."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Code not found

        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "invalid"},
            )

            assert response.status_code == 400
            assert "not found or expired" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_missing_device_data(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 400 when device data missing in cache."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            side_effect=[
                "AA:BB:CC:DD:EE:FF",  # mac_address found
                None,  # device data not found
            ]
        )

        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{test_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 400
            assert "device data not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_not_owned_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        from src.app.main import app
        from src.app.api.dependencies import get_cache_manager_dependency

        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            description="Other agent description",
            status=StatusEnum.enabled,
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        # Mock cache (even though we won't reach it due to ownership check)
        mock_cache = AsyncMock()
        app.dependency_overrides[get_cache_manager_dependency] = lambda: mock_cache

        try:
            response = await async_client.post(
                f"/api/v1/agents/{other_agent.id}/bind-device",
                headers=auth_headers,
                json={"code": "test123"},
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_cache_manager_dependency, None)

    @pytest.mark.asyncio
    async def test_bind_device_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/bind-device",
            json={"code": "test123"},
        )

        assert response.status_code == 401


class TestDeleteDeviceFromAgent:
    """Tests for DELETE /agents/{agent_id}/device - delete device from agent."""

    @pytest.mark.asyncio
    async def test_delete_device_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_device: Agent,
        clean_database,
    ):
        """Should delete device successfully."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_device.id}/device",
            headers=auth_headers,
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_device_clears_agent_references(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_device: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should clear agent device_id and device_mac_address."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_device.id}/device",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify agent device references cleared
        await async_session.refresh(test_agent_with_device)
        assert test_agent_with_device.device_id is None
        assert test_agent_with_device.device_mac_address is None

    @pytest.mark.asyncio
    async def test_delete_device_when_no_device_bound(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 404 when no device is bound."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}/device",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "no device bound" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_device_not_owned_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        # Create agent with device for superuser
        other_device = Device(
            user_id=test_superuser.id,
            mac_address="XX:XX:XX:XX:XX:XX",
            device_name="Other Device",
            board="ESP32",
            firmware_version="1.0.0",
        )
        async_session.add(other_device)
        await async_session.commit()
        await async_session.refresh(other_device)

        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            description="Other agent description",
            status=StatusEnum.enabled,
            device_id=other_device.id,
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_agent)

        response = await async_client.delete(
            f"/api/v1/agents/{other_agent.id}/device",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_device_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent_with_device: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_device.id}/device"
        )

        assert response.status_code == 401


# ========== Edge Cases and Integration Tests ==========


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    @pytest.mark.asyncio
    async def test_pagination_with_invalid_params(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should handle invalid pagination parameters."""
        # Page must be >= 1
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
            params={"page": 0, "page_size": 10},
        )
        assert response.status_code == 422

        # Page size must be >= 1 and <= 100
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
            params={"page": 1, "page_size": 0},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_with_max_page_size(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should cap page_size at 100."""
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
            params={"page": 1, "page_size": 101},
        )
        # Should return 422 validation error for page_size > 100
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_cross_user_isolation(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        superuser_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should isolate agents between users."""
        # Regular user can see their agent
        response = await async_client.get(
            "/api/v1/agents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        user_agents = response.json()["data"]

        # Superuser can't see regular user's agents
        response = await async_client.get(
            "/api/v1/agents",
            headers=superuser_headers,
        )
        assert response.status_code == 200
        superuser_agents = response.json()["data"]

        # Verify isolation
        user_agent_ids = [a["id"] for a in user_agents]
        superuser_agent_ids = [a["id"] for a in superuser_agents]
        assert str(test_agent.id) in user_agent_ids
        assert str(test_agent.id) not in superuser_agent_ids

    @pytest.mark.asyncio
    async def test_referential_integrity_device_delete(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_device: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should handle device deletion with referential integrity."""
        device_id = test_agent_with_device.device_id

        # Delete device via endpoint
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent_with_device.id}/device",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify agent.device_id becomes NULL
        await async_session.refresh(test_agent_with_device)
        assert test_agent_with_device.device_id is None


# ========== Webhook Configuration Tests ==========


class TestWebhookConfiguration:
    """Tests for webhook configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_webhook_config_no_key_generated(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should return webhook config with None api_key when not generated."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        webhook_config = data["data"]
        assert webhook_config["agent_id"] == str(test_agent.id)
        assert webhook_config["api_key"] is None

    @pytest.mark.asyncio
    async def test_create_webhook_config_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should generate a new API key."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Webhook API key generated successfully" in data["message"]

        webhook_config = data["data"]
        assert webhook_config["agent_id"] == str(test_agent.id)
        assert webhook_config["api_key"] is not None
        assert len(webhook_config["api_key"]) > 0

    @pytest.mark.asyncio
    async def test_create_webhook_config_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_webhook_config_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return 404 for non-existent agent."""
        response = await async_client.post(
            "/api/v1/agents/non-existent-id/webhook-config",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_webhook_config_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should delete API key."""
        # First create a key
        create_response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        api_key = create_response.json()["data"]["api_key"]
        assert api_key is not None

        # Then delete it
        delete_response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["success"] is True
        assert (
            "Webhook API key deleted successfully" in delete_response.json()["message"]
        )

        # Verify it's gone
        get_response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"]["api_key"] is None

    @pytest.mark.asyncio
    async def test_delete_webhook_config_unauthenticated(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.delete(
            f"/api/v1/agents/{test_agent.id}/webhook-config"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_webhook_config_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return 404 for non-existent agent."""
        response = await async_client.delete(
            "/api/v1/agents/non-existent-id/webhook-config",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_api_key_is_unique(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_agents: list[Agent],
        clean_database,
    ):
        """Should generate unique API keys for different agents."""
        agent1 = multiple_agents[0]
        agent2 = multiple_agents[1]

        response1 = await async_client.post(
            f"/api/v1/agents/{agent1.id}/webhook-config",
            headers=auth_headers,
        )
        response2 = await async_client.post(
            f"/api/v1/agents/{agent2.id}/webhook-config",
            headers=auth_headers,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        api_key1 = response1.json()["data"]["api_key"]
        api_key2 = response2.json()["data"]["api_key"]

        assert api_key1 != api_key2


# ========== Webhook Authentication Tests ==========


class TestWebhookHandler:
    """Tests for webhook endpoint authentication."""

    @pytest.mark.asyncio
    async def test_webhook_valid_token_query_param(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should accept valid API key in query parameter."""
        # First generate a key
        create_response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        api_key = create_response.json()["data"]["api_key"]

        # Then use it for webhook
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook",
            params={"token": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Webhook authenticated successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_webhook_valid_token_header(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should accept valid API key in X-Agent-Token header."""
        # First generate a key
        create_response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        api_key = create_response.json()["data"]["api_key"]

        # Then use it for webhook
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook",
            headers={"X-Agent-Token": api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Webhook authenticated successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_webhook_invalid_token(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should reject invalid API key."""
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook",
            params={"token": "invalid_token_12345"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_missing_token(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should reject request without API key."""
        response = await async_client.post(f"/api/v1/agents/{test_agent.id}/webhook")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_no_key_configured(
        self,
        async_client: AsyncClient,
        test_agent: Agent,
        clean_database,
    ):
        """Should reject request when API key not configured for agent."""
        # Don't generate a key, just try to access webhook
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook",
            params={"token": "some-token"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_non_existent_agent(
        self,
        async_client: AsyncClient,
        clean_database,
    ):
        """Should return 404 for non-existent agent."""
        response = await async_client.post(
            "/api/v1/agents/non-existent-id/webhook",
            params={"token": "some-token"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_token_priority(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        clean_database,
    ):
        """Should prefer query param token over header when both present."""
        # Generate a key
        create_response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook-config",
            headers=auth_headers,
        )
        valid_token = create_response.json()["data"]["api_key"]
        invalid_token = "invalid_token"

        # Valid in query, invalid in header
        response = await async_client.post(
            f"/api/v1/agents/{test_agent.id}/webhook",
            params={"token": valid_token},
            headers={"X-Agent-Token": invalid_token},
        )

        # Should succeed because query param is used
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
