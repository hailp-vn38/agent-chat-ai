"""
Integration tests for crud_agent.py using real database.

Tests all CRUDAgent methods with actual SQLAlchemy operations and joins.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.crud.crud_agent import crud_agent
from src.app.models.agent import Agent
from src.app.models.user import User
from src.app.models.device import Device
from src.app.models.agent_template import AgentTemplate
from src.app.schemas.agent import (
    AgentCreateInternal,
    AgentRead,
    AgentUpdateInternal,
)
from tests.conftest import fake


# ============================================================================
# BASIC CRUD OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_get_by_id_success(
    async_session: AsyncSession,
    test_agent: Agent,
    clean_database,
):
    """Test get_by_id returns agent when exists."""
    result = await crud_agent.get_by_id(db=async_session, id=test_agent.id)

    assert result is not None
    assert isinstance(result, AgentRead)
    assert result.id == test_agent.id
    assert result.agent_name == test_agent.agent_name
    assert result.user_id == test_agent.user_id


@pytest.mark.asyncio
async def test_get_by_id_not_found(
    async_session: AsyncSession,
    clean_database,
):
    """Test get_by_id returns None for non-existent agent."""
    from uuid6 import uuid7

    fake_id = str(uuid7())
    result = await crud_agent.get_by_id(db=async_session, id=fake_id)

    assert result is None


@pytest.mark.asyncio
async def test_create_agent_safe_success(
    async_session: AsyncSession,
    test_user: User,
    clean_database,
):
    """Test create_agent_safe creates agent successfully."""
    from src.app.core.enums import StatusEnum

    agent_data = AgentCreateInternal(
        user_id=test_user.id,
        agent_name=f"New Agent {fake.word()}",
        description="New agent description",
        status=StatusEnum.enabled,
    )

    result = await crud_agent.create_agent_safe(
        db=async_session, agent_create_internal=agent_data
    )

    assert result is not None
    assert isinstance(result, AgentRead)
    assert result.agent_name == agent_data.agent_name
    assert result.user_id == test_user.id
    assert result.description == agent_data.description


@pytest.mark.asyncio
async def test_create_agent_safe_duplicate_name(
    async_session: AsyncSession,
    test_user: User,
    test_agent: Agent,
    clean_database,
):
    """Test create_agent_safe raises ValueError for duplicate name."""
    from src.app.core.enums import StatusEnum

    agent_data = AgentCreateInternal(
        user_id=test_user.id,
        agent_name=test_agent.agent_name,  # Same name as existing agent
        description="Duplicate agent",
        status=StatusEnum.enabled,
    )

    with pytest.raises(ValueError, match="already exists"):
        await crud_agent.create_agent_safe(
            db=async_session, agent_create_internal=agent_data
        )


@pytest.mark.asyncio
async def test_create_agent_safe_same_name_different_user(
    async_session: AsyncSession,
    test_user: User,
    test_superuser: User,
    test_agent: Agent,
    clean_database,
):
    """Test create_agent_safe allows same name for different users."""
    from src.app.core.enums import StatusEnum

    agent_data = AgentCreateInternal(
        user_id=test_superuser.id,  # Different user
        agent_name=test_agent.agent_name,  # Same name
        description="Same name, different user",
        status=StatusEnum.enabled,
    )

    result = await crud_agent.create_agent_safe(
        db=async_session, agent_create_internal=agent_data
    )

    assert result is not None
    assert result.agent_name == test_agent.agent_name
    assert result.user_id == test_superuser.id
    assert result.user_id != test_agent.user_id


# ============================================================================
# TEMPLATE OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_change_agent_template_success(
    async_session: AsyncSession,
    test_agent: Agent,
    test_agent_template: AgentTemplate,
    clean_database,
):
    """Test change_agent_template updates template_id and activates template."""
    # Create a second template (inactive)
    from src.app.models.agent_template import AgentTemplate

    new_template = AgentTemplate(
        user_id=test_agent.user_id,
        agent_id=test_agent.id,
        agent_name=test_agent.agent_name,
        prompt="Bạn là trợ lý AI.",
        is_active=False,
    )
    async_session.add(new_template)
    await async_session.commit()
    await async_session.refresh(new_template)

    # Change to new template
    result = await crud_agent.change_agent_template(
        db=async_session,
        agent_id=test_agent.id,
        template_id=new_template.id,
    )

    assert result is not None
    assert result.template_id == new_template.id

    # Verify old template is deactivated
    await async_session.refresh(test_agent_template)
    assert test_agent_template.is_active is False

    # Verify new template is activated
    await async_session.refresh(new_template)
    assert new_template.is_active is True


@pytest.mark.asyncio
async def test_get_list_agent_template_success(
    async_session: AsyncSession,
    test_agent: Agent,
    test_agent_template: AgentTemplate,
    clean_database,
):
    """Test get_list_agent_template returns templates with pagination."""
    # Create additional templates
    from src.app.models.agent_template import AgentTemplate

    for i in range(3):
        template = AgentTemplate(
            user_id=test_agent.user_id,
            agent_id=test_agent.id,
            agent_name=test_agent.agent_name,
            prompt=f"Prompt {i}",
            is_active=False,
        )
        async_session.add(template)
    await async_session.commit()

    # Test pagination
    result = await crud_agent.get_list_agent_template(
        db=async_session,
        agent_id=test_agent.id,
        offset=0,
        limit=2,
    )

    assert result is not None
    assert "data" in result
    assert "total_count" in result
    assert len(result["data"]) == 2
    assert result["total_count"] == 4  # 1 from fixture + 3 new
    assert result["offset"] == 0
    assert result["limit"] == 2


@pytest.mark.asyncio
async def test_get_list_agent_template_empty(
    async_session: AsyncSession,
    test_agent: Agent,
    clean_database,
):
    """Test get_list_agent_template returns empty list for agent without templates."""
    result = await crud_agent.get_list_agent_template(
        db=async_session,
        agent_id=test_agent.id,
        offset=0,
        limit=10,
    )

    assert result is not None
    assert result["data"] == []
    assert result["total_count"] == 0


# ============================================================================
# JOIN OPERATIONS
# ============================================================================


@pytest.mark.asyncio
async def test_get_agent_with_device_success(
    async_session: AsyncSession,
    test_user: User,
    test_agent_with_device: Agent,
    test_device: Device,
    clean_database,
):
    """Test get_agent_with_device returns agent with device."""
    result = await crud_agent.get_agent_with_device(
        db=async_session,
        agent_id=test_agent_with_device.id,
        user_id=test_user.id,
    )

    assert result is not None
    assert "device" in result
    assert result["device"] is not None
    assert result["device"]["id"] == test_device.id
    assert result["device"]["mac_address"] == test_device.mac_address


@pytest.mark.asyncio
async def test_get_agent_with_device_no_device(
    async_session: AsyncSession,
    test_user: User,
    test_agent: Agent,
    clean_database,
):
    """Test get_agent_with_device returns agent with device=None when not bound."""
    result = await crud_agent.get_agent_with_device(
        db=async_session,
        agent_id=test_agent.id,
        user_id=test_user.id,
    )

    assert result is not None
    assert "device" in result
    assert result["device"] is None


@pytest.mark.asyncio
async def test_get_agent_with_device_wrong_owner(
    async_session: AsyncSession,
    test_user: User,
    test_superuser: User,
    test_agent: Agent,
    clean_database,
):
    """Test get_agent_with_device returns None for non-owner user."""
    result = await crud_agent.get_agent_with_device(
        db=async_session,
        agent_id=test_agent.id,
        user_id=test_superuser.id,  # Different user
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_agent_with_device_and_templates_success(
    async_session: AsyncSession,
    test_user: User,
    test_agent_with_device: Agent,
    test_device: Device,
    clean_database,
):
    """Test get_agent_with_device_and_templates returns full data."""
    # Create templates for agent
    from src.app.models.agent_template import AgentTemplate

    for i in range(3):
        template = AgentTemplate(
            user_id=test_user.id,
            agent_id=test_agent_with_device.id,
            agent_name=test_agent_with_device.agent_name,
            prompt=f"Prompt {i}",
            is_active=(i == 0),
        )
        async_session.add(template)
    await async_session.commit()

    result = await crud_agent.get_agent_with_device_and_templates(
        db=async_session,
        agent_id=test_agent_with_device.id,
        user_id=test_user.id,
        offset=0,
        limit=10,
    )

    assert result is not None
    assert "agent" in result
    assert "device" in result
    assert "templates" in result
    assert result["agent"].id == test_agent_with_device.id
    assert result["device"].id == test_device.id
    assert len(result["templates"]) == 3


@pytest.mark.asyncio
async def test_get_agent_with_device_and_templates_pagination(
    async_session: AsyncSession,
    test_user: User,
    test_agent: Agent,
    clean_database,
):
    """Test get_agent_with_device_and_templates paginates templates correctly."""
    # Create 5 templates
    from src.app.models.agent_template import AgentTemplate

    for i in range(5):
        template = AgentTemplate(
            user_id=test_user.id,
            agent_id=test_agent.id,
            agent_name=test_agent.agent_name,
            prompt=f"Prompt {i}",
            is_active=False,
        )
        async_session.add(template)
    await async_session.commit()

    # Test pagination
    result = await crud_agent.get_agent_with_device_and_templates(
        db=async_session,
        agent_id=test_agent.id,
        user_id=test_user.id,
        offset=2,
        limit=2,
    )

    assert result is not None
    assert len(result["templates"]) == 2


@pytest.mark.asyncio
async def test_get_agent_by_mac_address_success(
    async_session: AsyncSession,
    test_agent_with_device: Agent,
    test_device: Device,
    clean_database,
):
    """Test get_agent_by_mac_address returns agent by device MAC."""
    result = await crud_agent.get_agent_by_mac_address(
        db=async_session,
        mac_address=test_device.mac_address,
    )

    assert result is not None
    assert result["id"] == test_agent_with_device.id
    assert "device" in result
    assert result["device"]["mac_address"] == test_device.mac_address


@pytest.mark.asyncio
async def test_get_agent_by_mac_address_not_found(
    async_session: AsyncSession,
    clean_database,
):
    """Test get_agent_by_mac_address returns None for non-existent MAC."""
    result = await crud_agent.get_agent_by_mac_address(
        db=async_session,
        mac_address="FF:FF:FF:FF:FF:FF",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_agent_by_mac_address_with_template(
    async_session: AsyncSession,
    test_agent_with_device: Agent,
    test_device: Device,
    clean_database,
):
    """Test get_agent_by_mac_address includes template and providers when template_id is set."""
    # Create template and assign to agent
    from src.app.models.agent_template import AgentTemplate

    template = AgentTemplate(
        user_id=test_agent_with_device.user_id,
        agent_id=test_agent_with_device.id,
        agent_name=test_agent_with_device.agent_name,
        prompt="Test prompt",
        is_active=True,
        # Provider FK fields are NULL - will use config.yml fallback
        ASR=None,
        LLM=None,
        TTS=None,
    )
    async_session.add(template)
    await async_session.commit()
    await async_session.refresh(template)

    # Update agent with template_id
    test_agent_with_device.template_id = template.id
    await async_session.commit()

    result = await crud_agent.get_agent_by_mac_address(
        db=async_session,
        mac_address=test_device.mac_address,
    )

    assert result is not None
    assert "template" in result
    assert result["template"]["id"] == template.id
    # New: providers key should be present (even if all NULL)
    assert "providers" in result
    assert isinstance(result["providers"], dict)
    # All providers should be NULL since template has no FK references
    assert result["providers"]["ASR"] is None
    assert result["providers"]["LLM"] is None
    assert result["providers"]["TTS"] is None


# ============================================================================
# DEPRECATED METHODS (Backward Compatibility)
# ============================================================================


@pytest.mark.asyncio
async def test_get_detail_agent_success(
    async_session: AsyncSession,
    test_agent_with_device: Agent,
    test_device: Device,
    clean_database,
):
    """Test get_detail_agent returns agent with device and templates."""
    # Create templates
    from src.app.models.agent_template import AgentTemplate

    for i in range(2):
        template = AgentTemplate(
            user_id=test_agent_with_device.user_id,
            agent_id=test_agent_with_device.id,
            agent_name=test_agent_with_device.agent_name,
            prompt=f"Prompt {i}",
            is_active=False,
        )
        async_session.add(template)
    await async_session.commit()

    result = await crud_agent.get_detail_agent(
        db=async_session,
        agent_id=test_agent_with_device.id,
        offset=0,
        limit=10,
    )

    assert result is not None
    assert "agent" in result
    assert "device" in result
    assert "templates" in result
    assert result["agent"].id == test_agent_with_device.id
    assert result["device"].id == test_device.id
    assert len(result["templates"]) == 2


@pytest.mark.asyncio
async def test_get_detail_agent_not_found(
    async_session: AsyncSession,
    clean_database,
):
    """Test get_detail_agent returns None values for non-existent agent."""
    from uuid6 import uuid7

    fake_id = str(uuid7())
    result = await crud_agent.get_detail_agent(
        db=async_session,
        agent_id=fake_id,
        offset=0,
        limit=10,
    )

    assert result is not None
    assert result["agent"] is None
    assert result["device"] is None
    assert result["templates"] == []


# ============================================================================
# EDGE CASES & FILTERS
# ============================================================================


@pytest.mark.asyncio
async def test_soft_delete_filtering(
    async_session: AsyncSession,
    test_user: User,
    multiple_agents: list[Agent],
    clean_database,
):
    """Test that soft-deleted agents are filtered out in get_multi."""
    result = await crud_agent.get_multi(
        db=async_session,
        user_id=test_user.id,
        is_deleted=False,
        offset=0,
        limit=10,
    )

    assert result is not None
    data = result.get("data", [])
    # Should return 4 agents (5 total - 1 soft-deleted)
    assert len(data) == 4

    # Verify soft-deleted agent is not in results
    deleted_agent = multiple_agents[4]
    assert deleted_agent.is_deleted is True
    agent_ids = [agent["id"] for agent in data]
    assert deleted_agent.id not in agent_ids


@pytest.mark.asyncio
async def test_pagination_offset_limit(
    async_session: AsyncSession,
    test_user: User,
    multiple_agents: list[Agent],
    clean_database,
):
    """Test pagination with offset and limit."""
    # Get first 2 agents
    result1 = await crud_agent.get_multi(
        db=async_session,
        user_id=test_user.id,
        is_deleted=False,
        offset=0,
        limit=2,
    )

    assert len(result1["data"]) == 2

    # Get next 2 agents
    result2 = await crud_agent.get_multi(
        db=async_session,
        user_id=test_user.id,
        is_deleted=False,
        offset=2,
        limit=2,
    )

    assert len(result2["data"]) == 2

    # Ensure no overlap
    ids1 = {agent["id"] for agent in result1["data"]}
    ids2 = {agent["id"] for agent in result2["data"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_ownership_filtering(
    async_session: AsyncSession,
    test_user: User,
    test_superuser: User,
    clean_database,
):
    """Test that users only see their own agents."""
    # Create agents for both users
    from src.app.models.agent import Agent
    from src.app.core.enums import StatusEnum

    user_agent = Agent(
        user_id=test_user.id,
        agent_name="User Agent",
        description="User's agent",
        status=StatusEnum.enabled,
    )
    superuser_agent = Agent(
        user_id=test_superuser.id,
        agent_name="Superuser Agent",
        description="Superuser's agent",
        status=StatusEnum.enabled,
    )
    async_session.add_all([user_agent, superuser_agent])
    await async_session.commit()

    # Test user can only see their agent
    user_result = await crud_agent.get_multi(
        db=async_session,
        user_id=test_user.id,
        is_deleted=False,
    )

    user_ids = [agent["id"] for agent in user_result["data"]]
    assert user_agent.id in user_ids
    assert superuser_agent.id not in user_ids

    # Test superuser can only see their agent
    superuser_result = await crud_agent.get_multi(
        db=async_session,
        user_id=test_superuser.id,
        is_deleted=False,
    )

    superuser_ids = [agent["id"] for agent in superuser_result["data"]]
    assert superuser_agent.id in superuser_ids
    assert user_agent.id not in superuser_ids
