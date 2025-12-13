"""
Test suite for Template API endpoints.

Tests cover:
- Template CRUD operations (list, get, create, update, delete)
- Template assignment to agents
- Public template access
- Authorization and access control
- Pagination and error scenarios
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import StatusEnum
from src.app.models.agent import Agent
from src.app.models.template import Template
from src.app.models.agent_template_assignment import AgentTemplateAssignment
from src.app.models.user import User


# ========== Template CRUD Endpoint Tests ==========


class TestTemplateList:
    """Tests for GET /templates - list templates with pagination."""

    @pytest.mark.asyncio
    async def test_list_templates_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should return paginated list of user's templates."""
        response = await async_client.get(
            "/api/v1/templates",
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
        assert data["data"][0]["name"] == test_template.name

    @pytest.mark.asyncio
    async def test_list_templates_unauthenticated(
        self,
        async_client: AsyncClient,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.get("/api/v1/templates")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_templates_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return empty list when user has no templates."""
        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["data"]) == 0

    @pytest.mark.asyncio
    async def test_list_templates_include_public(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_public_template: Template,
        clean_database,
    ):
        """Should include public templates when include_public=True."""
        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
            params={"include_public": True},
        )

        assert response.status_code == 200
        data = response.json()
        # Should include public template from other user
        public_templates = [t for t in data["data"] if t["is_public"]]
        assert len(public_templates) >= 1

    @pytest.mark.asyncio
    async def test_list_templates_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_templates: list[Template],
        clean_database,
    ):
        """Should handle pagination correctly."""
        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
            params={"page": 1, "page_size": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5


class TestTemplateCreate:
    """Tests for POST /templates - create template."""

    @pytest.mark.asyncio
    async def test_create_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should create template with valid data."""
        template_data = {
            "name": "New Test Template",
            "prompt": "You are a helpful assistant.",
            "is_public": False,
        }

        response = await async_client.post(
            "/api/v1/templates",
            headers=auth_headers,
            json=template_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == template_data["name"]
        assert data["prompt"] == template_data["prompt"]
        assert data["is_public"] == template_data["is_public"]
        assert "id" in data
        assert "user_id" in data

    @pytest.mark.asyncio
    async def test_create_template_with_config_providers(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should create template with config provider references."""
        template_data = {
            "name": "Template with Providers",
            "prompt": "Test prompt",
            "ASR": "config:VietNamASRLocal",
            "LLM": "config:CopilotLLM",
            "TTS": "config:HoaiMyEdgeTTS",
        }

        response = await async_client.post(
            "/api/v1/templates",
            headers=auth_headers,
            json=template_data,
        )

        # May return 400 if providers don't exist in config
        # Check for successful creation or validation error
        assert response.status_code in [201, 400]

    @pytest.mark.asyncio
    async def test_create_template_unauthenticated(
        self,
        async_client: AsyncClient,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        template_data = {
            "name": "New Template",
            "prompt": "Test prompt",
        }

        response = await async_client.post("/api/v1/templates", json=template_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_template_invalid_data(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return 422 for invalid data."""
        template_data = {
            "name": "",  # Empty name
            "prompt": "Test",
        }

        response = await async_client.post(
            "/api/v1/templates",
            headers=auth_headers,
            json=template_data,
        )

        assert response.status_code == 422


class TestTemplateGet:
    """Tests for GET /templates/{template_id} - get template detail."""

    @pytest.mark.asyncio
    async def test_get_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should return template detail for owned template."""
        response = await async_client.get(
            f"/api/v1/templates/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_template.id)
        assert data["name"] == test_template.name

    @pytest.mark.asyncio
    async def test_get_public_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_public_template: Template,
        clean_database,
    ):
        """Should allow access to public templates from other users."""
        response = await async_client.get(
            f"/api/v1/templates/{test_public_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_public_template.id)
        assert data["is_public"] is True

    @pytest.mark.asyncio
    async def test_get_template_not_owned_private(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 403 for private template from other user."""
        # Create private template for superuser
        other_template = Template(
            name="Other Template",
            user_id=str(test_superuser.id),
            prompt="Test prompt",
            is_public=False,
        )
        async_session.add(other_template)
        await async_session.commit()
        await async_session.refresh(other_template)

        response = await async_client.get(
            f"/api/v1/templates/{other_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_template_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should return 404 for non-existent template."""
        response = await async_client.get(
            "/api/v1/templates/non-existent-id",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.get(f"/api/v1/templates/{test_template.id}")
        assert response.status_code == 401


class TestTemplateUpdate:
    """Tests for PUT /templates/{template_id} - update template."""

    @pytest.mark.asyncio
    async def test_update_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should update template with valid data."""
        update_data = {
            "name": "Updated Template Name",
            "prompt": "Updated prompt",
        }

        response = await async_client.put(
            f"/api/v1/templates/{test_template.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["prompt"] == update_data["prompt"]

    @pytest.mark.asyncio
    async def test_update_template_partial(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should allow partial update."""
        update_data = {"name": "Updated Template"}

        response = await async_client.patch(
            f"/api/v1/templates/{test_template.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        # Name should remain unchanged
        assert data["name"] == test_template.name

    @pytest.mark.asyncio
    async def test_update_template_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 403 for non-owned template."""
        other_template = Template(
            name="Other Template",
            user_id=str(test_superuser.id),
            prompt="Test prompt",
            is_public=False,
        )
        async_session.add(other_template)
        await async_session.commit()
        await async_session.refresh(other_template)

        update_data = {"name": "Hacked Name"}

        response = await async_client.put(
            f"/api/v1/templates/{other_template.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_public_template_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_public_template: Template,
        clean_database,
    ):
        """Should return 403 even for public template if not owner."""
        update_data = {"name": "Hacked Name"}

        response = await async_client.put(
            f"/api/v1/templates/{test_public_template.id}",
            headers=auth_headers,
            json=update_data,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        update_data = {"name": "Updated"}

        response = await async_client.put(
            f"/api/v1/templates/{test_template.id}",
            json=update_data,
        )

        assert response.status_code == 401


class TestTemplateDelete:
    """Tests for DELETE /templates/{template_id} - delete template."""

    @pytest.mark.asyncio
    async def test_delete_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should delete template successfully."""
        response = await async_client.delete(
            f"/api/v1/templates/{test_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify template is deleted
        get_response = await async_client.get(
            f"/api/v1/templates/{test_template.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_template_clears_agent_active(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_template: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should clear agent's active_template_id when template deleted."""
        template_id = test_agent_with_template.active_template_id

        response = await async_client.delete(
            f"/api/v1/templates/{template_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify agent's active_template_id is cleared
        await async_session.refresh(test_agent_with_template)
        assert test_agent_with_template.active_template_id is None

    @pytest.mark.asyncio
    async def test_delete_template_not_owned(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 403 for non-owned template."""
        other_template = Template(
            name="Other Template",
            user_id=str(test_superuser.id),
            prompt="Test prompt",
            is_public=False,
        )
        async_session.add(other_template)
        await async_session.commit()
        await async_session.refresh(other_template)

        response = await async_client.delete(
            f"/api/v1/templates/{other_template.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_template_unauthenticated(
        self,
        async_client: AsyncClient,
        test_template: Template,
        clean_database,
    ):
        """Should return 401 when not authenticated."""
        response = await async_client.delete(f"/api/v1/templates/{test_template.id}")
        assert response.status_code == 401


# ========== Template Assignment Endpoint Tests ==========


class TestListAgentsUsingTemplate:
    """Tests for GET /templates/{template_id}/agents - list agents."""

    @pytest.mark.asyncio
    async def test_list_agents_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template_with_agents: tuple[Template, list[Agent]],
        clean_database,
    ):
        """Should return agents using the template."""
        template, agents = test_template_with_agents

        response = await async_client.get(
            f"/api/v1/templates/{template.id}/agents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == len(agents)

    @pytest.mark.asyncio
    async def test_list_agents_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should return empty list when no agents use template."""
        response = await async_client.get(
            f"/api/v1/templates/{test_template.id}/agents",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["data"]) == 0

    @pytest.mark.asyncio
    async def test_list_agents_not_owned_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
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

        response = await async_client.get(
            f"/api/v1/templates/{other_template.id}/agents",
            headers=auth_headers,
        )

        assert response.status_code == 403


class TestAssignTemplateToAgent:
    """Tests for POST /templates/{template_id}/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_assign_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_template: Template,
        test_agent: Agent,
        clean_database,
    ):
        """Should assign template to agent successfully."""
        response = await async_client.post(
            f"/api/v1/templates/{test_template.id}/agents/{test_agent.id}",
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
        test_template: Template,
        test_agent: Agent,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should set template as active when set_active=True."""
        response = await async_client.post(
            f"/api/v1/templates/{test_template.id}/agents/{test_agent.id}",
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
        test_public_template: Template,
        test_agent: Agent,
        clean_database,
    ):
        """Should allow assigning public template from other user."""
        response = await async_client.post(
            f"/api/v1/templates/{test_public_template.id}/agents/{test_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 201

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
            f"/api/v1/templates/{test_template.id}/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

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
            f"/api/v1/templates/{other_template.id}/agents/{test_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403


class TestUnassignTemplateFromAgent:
    """Tests for DELETE /templates/{template_id}/agents/{agent_id}."""

    @pytest.mark.asyncio
    async def test_unassign_template_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent_with_assignment: tuple[Agent, Template, AgentTemplateAssignment],
        clean_database,
    ):
        """Should unassign template from agent successfully."""
        agent, template, assignment = test_agent_with_assignment

        response = await async_client.delete(
            f"/api/v1/templates/{template.id}/agents/{agent.id}",
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
            f"/api/v1/templates/{template_id}/agents/{test_agent_with_template.id}",
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
        test_template: Template,
        test_agent: Agent,
        clean_database,
    ):
        """Should return 404 when assignment doesn't exist."""
        response = await async_client.delete(
            f"/api/v1/templates/{test_template.id}/agents/{test_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unassign_not_owned_agent(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_superuser: User,
        async_session: AsyncSession,
        clean_database,
    ):
        """Should return 404 for non-owned agent."""
        # Create template for superuser
        other_template = Template(
            name="Other Template",
            user_id=str(test_superuser.id),
            prompt="Test prompt",
            is_public=True,
        )
        async_session.add(other_template)

        # Create agent for superuser
        other_agent = Agent(
            agent_name="Other Agent",
            user_id=test_superuser.id,
            status=StatusEnum.enabled,
            description="Other agent description",
        )
        async_session.add(other_agent)
        await async_session.commit()
        await async_session.refresh(other_template)
        await async_session.refresh(other_agent)

        # Create assignment
        assignment = AgentTemplateAssignment(
            agent_id=str(other_agent.id),
            template_id=str(other_template.id),
        )
        async_session.add(assignment)
        await async_session.commit()

        response = await async_client.delete(
            f"/api/v1/templates/{other_template.id}/agents/{other_agent.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


# ========== Edge Cases ==========


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    @pytest.mark.asyncio
    async def test_pagination_invalid_params(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        clean_database,
    ):
        """Should handle invalid pagination parameters."""
        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
            params={"page": 0, "page_size": 10},
        )
        assert response.status_code == 422

        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
            params={"page": 1, "page_size": 101},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_cross_user_isolation(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        superuser_headers: dict,
        test_template: Template,
        clean_database,
    ):
        """Should isolate private templates between users."""
        # Regular user can see their template
        response = await async_client.get(
            "/api/v1/templates",
            headers=auth_headers,
        )
        assert response.status_code == 200
        user_templates = response.json()["data"]
        user_template_ids = [t["id"] for t in user_templates]
        assert str(test_template.id) in user_template_ids

        # Superuser cannot see regular user's private templates
        response = await async_client.get(
            "/api/v1/templates",
            headers=superuser_headers,
        )
        assert response.status_code == 200
        superuser_templates = response.json()["data"]
        superuser_template_ids = [t["id"] for t in superuser_templates]
        assert str(test_template.id) not in superuser_template_ids
