"""
Integration tests for normalized Agent MCP Selection system.

Tests the complete flow of:
- Creating/updating Agent MCP selections
- Resolving MCP references (db: and config: formats)
- Validating reference formats
- Fetching MCP configs with metadata
- Database schema consistency
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from src.app.models.agent import Agent
from src.app.models.agent_mcp_selection import (
    AgentMCPSelection,
    AgentMCPServerSelected,
)
from src.app.models.server_mcp_config import ServerMCPConfig
from src.app.models.user import User
from src.app.schemas.agent import MCPSelection, MCPServerReference
from src.app.schemas.server_mcp_config import ServerMCPConfigCreate
from src.app.services.agent_mcp_selection_service import (
    AgentMCPSelectionService,
)
from src.app.services.mcp_metadata_resolver import MCPMetadataResolver
from src.app.services.mcp_reference_validator import MCPReferenceValidator
from src.app.crud.crud_agent_mcp_selection import (
    crud_agent_mcp_selection,
    crud_agent_mcp_server_selected,
)
from src.app.crud.crud_server_mcp_config import crud_server_mcp_config


# ========== MCPMetadataResolver Tests ==========


class TestMCPMetadataResolver:
    """Tests for metadata resolution from different sources."""

    @pytest.mark.asyncio
    async def test_resolve_from_db_success(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should resolve db: reference to ServerMCPConfig metadata."""
        # Create test MCP server
        mcp_config = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            args=["-m", "test"],
            env=None,
            description="Test MCP server",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp_config)
        await async_session.commit()

        # Resolve reference
        reference = f"db:{mcp_config.id}"
        resolved = await MCPMetadataResolver.resolve_from_db(
            reference=reference,
            user_id=test_user.id,
            db=async_session,
        )

        assert resolved is not None
        assert resolved["reference"] == reference
        assert resolved["mcp_name"] == "test_mcp"
        assert resolved["mcp_type"] == "stdio"
        assert resolved["mcp_description"] == "Test MCP server"

    @pytest.mark.asyncio
    async def test_resolve_from_db_not_found(
        self,
        async_session: AsyncSession,
        test_user: User,
    ):
        """Should raise ValueError for non-existent db: reference."""
        reference = f"db:{uuid7()}"
        with pytest.raises(ValueError, match="not found or you don't have permission"):
            await MCPMetadataResolver.resolve_from_db(
                reference=reference,
                user_id=test_user.id,
                db=async_session,
            )

    @pytest.mark.asyncio
    async def test_resolve_all_batch_success(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should batch resolve multiple references efficiently."""
        # Create test MCP servers
        mcp1 = ServerMCPConfig(
            user_id=test_user.id,
            name="mcp_1",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        mcp2 = ServerMCPConfig(
            user_id=test_user.id,
            name="mcp_2",
            type="sse",
            url="http://localhost:8000",
            is_active=True,
            is_deleted=False,
        )
        async_session.add_all([mcp1, mcp2])
        await async_session.commit()

        # Resolve batch
        references = [f"db:{mcp1.id}", f"db:{mcp2.id}"]
        resolved = await MCPMetadataResolver.resolve_all(
            references=references,
            user_id=test_user.id,
            db=async_session,
        )

        assert len(resolved) == 2
        assert resolved[0]["mcp_name"] == "mcp_1"
        assert resolved[1]["mcp_name"] == "mcp_2"


# ========== MCPReferenceValidator Tests ==========


class TestMCPReferenceValidator:
    """Tests for MCP reference format validation."""

    @pytest.mark.asyncio
    async def test_parse_db_reference(self):
        """Should parse db: reference correctly."""
        mcp_id = uuid7()
        reference = f"db:{mcp_id}"
        source, name = MCPReferenceValidator.parse_reference(reference)

        assert source == "db"
        assert name == str(mcp_id)

    @pytest.mark.asyncio
    async def test_parse_config_reference(self):
        """Should parse config: reference correctly."""
        reference = "config:openai_mcp"
        source, name = MCPReferenceValidator.parse_reference(reference)

        assert source == "config"
        assert name == "openai_mcp"

    @pytest.mark.asyncio
    async def test_parse_invalid_reference(self):
        """Should raise error for invalid reference format."""
        invalid_refs = [
            "invalid:uuid",  # not db: or config:
            "config:",  # missing name
            "notprefixed",  # no prefix
        ]

        for ref in invalid_refs:
            with pytest.raises(ValueError):
                MCPReferenceValidator.parse_reference(ref)

    @pytest.mark.asyncio
    async def test_validate_all_references_success(
        self,
        async_session: AsyncSession,
        test_user: User,
    ):
        """Should validate all references in batch."""
        mcp = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp)
        await async_session.commit()

        references = [f"db:{mcp.id}"]
        await MCPReferenceValidator.validate_all_mcp_references(
            references=references,
            user_id=test_user.id,
            db=async_session,
        )

        # Should not raise exception

    @pytest.mark.asyncio
    async def test_validate_all_references_failure(
        self,
        async_session: AsyncSession,
        test_user: User,
    ):
        """Should raise error for invalid references."""
        references = ["db:not-a-uuid"]

        with pytest.raises(ValueError):
            await MCPReferenceValidator.validate_all_mcp_references(
                references=references,
                user_id=test_user.id,
                db=async_session,
            )


# ========== AgentMCPSelectionService Tests ==========


class TestAgentMCPSelectionService:
    """Tests for agent MCP selection business logic."""

    @pytest.mark.asyncio
    async def test_get_selection_default_all_mode(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should create default selection with 'all' mode if not exists."""
        selection = await AgentMCPSelectionService.get_selection(
            agent_id=test_agent.id,
            user_id=test_user.id,
            db=async_session,
        )

        assert selection.mcp_selection_mode == "all"
        assert selection.agent_id == test_agent.id
        # Servers list should exist but be empty for 'all' mode
        assert isinstance(selection.servers, list)

    @pytest.mark.asyncio
    async def test_get_selection_selected_mode(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should retrieve selection with resolved server metadata."""
        # Create test MCP servers
        mcp1 = ServerMCPConfig(
            user_id=test_user.id,
            name="mcp_1",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        mcp2 = ServerMCPConfig(
            user_id=test_user.id,
            name="mcp_2",
            type="sse",
            url="http://localhost:8000",
            is_active=True,
            is_deleted=False,
        )
        async_session.add_all([mcp1, mcp2])
        await async_session.commit()

        # Create selection with 'selected' mode
        selection = MCPSelection(
            mode="selected",
            servers=[
                MCPServerReference(reference=f"db:{mcp1.id}"),
                MCPServerReference(reference=f"db:{mcp2.id}"),
            ],
        )

        updated = await AgentMCPSelectionService.update_selection(
            agent_id=test_agent.id,
            user_id=test_user.id,
            selection=selection,
            db=async_session,
        )

        assert updated.mcp_selection_mode == "selected"
        assert len(updated.servers) == 2
        assert updated.servers[0].mcp_name == "mcp_1"
        assert updated.servers[1].mcp_name == "mcp_2"

    @pytest.mark.asyncio
    async def test_update_selection_switch_to_all_mode(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should switch from 'selected' to 'all' mode and clear servers."""
        # Create initial 'selected' selection
        mcp = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp)
        await async_session.commit()

        selection = MCPSelection(
            mode="selected",
            servers=[MCPServerReference(reference=f"db:{mcp.id}")],
        )

        await AgentMCPSelectionService.update_selection(
            agent_id=test_agent.id,
            user_id=test_user.id,
            selection=selection,
            db=async_session,
        )

        # Switch to 'all' mode
        new_selection = MCPSelection(mode="all", servers=[])
        updated = await AgentMCPSelectionService.update_selection(
            agent_id=test_agent.id,
            user_id=test_user.id,
            selection=new_selection,
            db=async_session,
        )

        assert updated.mcp_selection_mode == "all"
        assert len(updated.servers) == 0

    @pytest.mark.asyncio
    async def test_update_selection_validation_failure(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should validate references before persisting."""
        # Try to select non-existent MCP
        selection = MCPSelection(
            mode="selected",
            servers=[
                MCPServerReference(reference=f"db:{uuid7()}"),  # non-existent
            ],
        )

        with pytest.raises(ValueError):
            await AgentMCPSelectionService.update_selection(
                agent_id=test_agent.id,
                user_id=test_user.id,
                selection=selection,
                db=async_session,
            )


# ========== CRUD Operations Tests ==========


class TestAgentMCPSelectionCRUD:
    """Tests for CRUD operations on normalized tables."""

    @pytest.mark.asyncio
    async def test_crud_create_selection(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should create new AgentMCPSelection record."""
        from src.app.schemas.agent import AgentMCPSelectionCreate

        created = await crud_agent_mcp_selection.create(
            db=async_session,
            object=AgentMCPSelectionCreate(
                agent_id=test_agent.id,
                mcp_selection_mode="all",
            ),
        )

        assert created.agent_id == test_agent.id
        assert created.mcp_selection_mode == "all"

    @pytest.mark.asyncio
    async def test_crud_get_joined(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should get selection with all joined server data."""
        # Create selection and servers
        selection = AgentMCPSelection(
            agent_id=test_agent.id,
            mcp_selection_mode="selected",
        )
        async_session.add(selection)
        await async_session.commit()

        mcp = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp)
        await async_session.commit()

        server_selected = AgentMCPServerSelected(
            agent_mcp_selection_id=selection.id,
            reference=f"db:{mcp.id}",
            mcp_name="test_mcp",
            mcp_type="stdio",
            mcp_description="Test MCP",
            source="user",
            is_active=True,
        )
        async_session.add(server_selected)
        await async_session.commit()

        # Get joined
        result = await crud_agent_mcp_selection.get_joined(
            db=async_session,
            agent_id=test_agent.id,
        )

        assert result is not None
        assert result.mcp_selection_mode == "selected"
        assert len(result.servers) == 1
        assert result.servers[0].mcp_name == "test_mcp"

    @pytest.mark.asyncio
    async def test_crud_delete_servers_on_selection_delete(
        self,
        async_session: AsyncSession,
        test_user: User,
        test_agent: Agent,
    ):
        """Should cascade delete servers when selection is deleted."""
        # Create selection with servers
        selection = AgentMCPSelection(
            agent_id=test_agent.id,
            mcp_selection_mode="selected",
        )
        async_session.add(selection)
        await async_session.commit()

        server_selected = AgentMCPServerSelected(
            agent_mcp_selection_id=selection.id,
            reference=f"db:{uuid7()}",
            mcp_name="test_mcp",
            mcp_type="stdio",
            source="user",
            is_active=True,
        )
        async_session.add(server_selected)
        await async_session.commit()

        # Delete selection
        await crud_agent_mcp_selection.delete(
            db=async_session,
            id=selection.id,
        )
        await async_session.commit()

        # Check server is also deleted
        servers = await crud_agent_mcp_server_selected.get_multi(
            db=async_session,
            agent_mcp_selection_id=selection.id,
        )
        assert len(servers.get("data", [])) == 0


# ========== API Endpoint Tests ==========


class TestAgentMCPSelectionEndpoints:
    """Tests for Agent MCP Selection API endpoints."""

    @pytest.mark.asyncio
    async def test_get_mcp_selection_endpoint(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        async_session: AsyncSession,
    ):
        """Should GET agent MCP selection with metadata."""
        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/mcp",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "agent_id" in data
        assert "mcp_selection_mode" in data
        assert "servers" in data

    @pytest.mark.asyncio
    async def test_put_mcp_selection_endpoint(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_user: User,
        async_session: AsyncSession,
    ):
        """Should PUT agent MCP selection with validation."""
        # Create test MCP
        mcp = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp)
        await async_session.commit()

        payload = {
            "mode": "selected",
            "servers": [
                {"reference": f"db:{mcp.id}"},
            ],
        }

        response = await async_client.put(
            f"/api/v1/agents/{test_agent.id}/mcp",
            headers=auth_headers,
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["mcp_selection_mode"] == "selected"
        assert len(data["servers"]) == 1

    @pytest.mark.asyncio
    async def test_get_available_mcp_servers_endpoint(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_agent: Agent,
        test_user: User,
        async_session: AsyncSession,
    ):
        """Should GET available MCP servers for current user."""
        # Create test MCPs
        mcp = ServerMCPConfig(
            user_id=test_user.id,
            name="test_mcp",
            type="stdio",
            command="python",
            is_active=True,
            is_deleted=False,
        )
        async_session.add(mcp)
        await async_session.commit()

        response = await async_client.get(
            f"/api/v1/agents/{test_agent.id}/mcp/available",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "mcp_servers" in data
        assert isinstance(data["mcp_servers"], list)


# ========== Database Schema Integrity Tests ==========


class TestMCPSelectionSchemaIntegrity:
    """Tests for database schema consistency and constraints."""

    @pytest.mark.asyncio
    async def test_unique_constraint_agent_mcp_selection(
        self,
        async_session: AsyncSession,
        test_agent: Agent,
    ):
        """Should enforce unique constraint on agent_id."""
        selection1 = AgentMCPSelection(
            agent_id=test_agent.id,
            mcp_selection_mode="all",
        )
        selection2 = AgentMCPSelection(
            agent_id=test_agent.id,
            mcp_selection_mode="selected",
        )

        async_session.add(selection1)
        await async_session.commit()

        async_session.add(selection2)

        # Should fail due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            await async_session.commit()

    @pytest.mark.asyncio
    async def test_unique_constraint_server_selection(
        self,
        async_session: AsyncSession,
        test_agent: Agent,
    ):
        """Should enforce unique constraint on (selection_id, reference)."""
        selection = AgentMCPSelection(
            agent_id=test_agent.id,
            mcp_selection_mode="selected",
        )
        async_session.add(selection)
        await async_session.commit()

        ref = f"db:{uuid7()}"
        server1 = AgentMCPServerSelected(
            agent_mcp_selection_id=selection.id,
            reference=ref,
            mcp_name="test",
            mcp_type="stdio",
            source="user",
            is_active=True,
        )
        server2 = AgentMCPServerSelected(
            agent_mcp_selection_id=selection.id,
            reference=ref,  # Same reference
            mcp_name="test",
            mcp_type="stdio",
            source="user",
            is_active=True,
        )

        async_session.add(server1)
        await async_session.commit()

        async_session.add(server2)

        # Should fail due to unique constraint
        with pytest.raises(Exception):
            await async_session.commit()
