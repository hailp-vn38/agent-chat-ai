"""
Tests for ServerMCPConfig model and CRUD operations.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.crud.crud_server_mcp_config import crud_server_mcp_config
from src.app.models.server_mcp_config import ServerMCPConfig
from src.app.schemas.server_mcp_config import (
    ServerMCPConfigCreate,
    ServerMCPConfigCreateInternal,
)


@pytest_asyncio.fixture
async def mcp_config_user(async_session: AsyncSession):
    """Create a test user for MCP config tests."""
    from src.app.models.user import User
    from src.app.core.security import get_password_hash
    from faker import Faker

    fake = Faker()
    user = User(
        name=fake.name(),
        email=fake.email(),
        hashed_password=get_password_hash("testpass123"),
        is_superuser=False,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_mcp_config(async_session: AsyncSession, mcp_config_user):
    """Test creating an MCP configuration."""
    config_data = ServerMCPConfigCreateInternal(
        name="test_mcp",
        description="Test MCP Server",
        type="stdio",
        command="npx",
        args=["mcp-server"],
        env={"DEBUG": "true"},
        user_id=str(mcp_config_user.id),
    )

    config = await crud_server_mcp_config.create(
        db=async_session,
        object=config_data,
    )

    assert config is not None
    assert config.name == "test_mcp"
    assert config.user_id == str(mcp_config_user.id)
    assert config.type == "stdio"


@pytest.mark.asyncio
async def test_mcp_config_constraints(async_session: AsyncSession, mcp_config_user):
    """Test MCP config database constraints."""
    # Test unique constraint: (user_id, name)
    config_data1 = ServerMCPConfigCreateInternal(
        name="unique_test",
        type="stdio",
        command="npx",
        user_id=str(mcp_config_user.id),
    )

    await crud_server_mcp_config.create(db=async_session, object=config_data1)

    # Try to create duplicate
    config_data2 = ServerMCPConfigCreateInternal(
        name="unique_test",
        type="stdio",
        command="node",
        user_id=str(mcp_config_user.id),
    )

    with pytest.raises(Exception):  # Should raise unique constraint violation
        await crud_server_mcp_config.create(db=async_session, object=config_data2)


@pytest.mark.asyncio
async def test_soft_delete_mcp_config(async_session: AsyncSession, mcp_config_user):
    """Test soft deleting an MCP configuration."""
    config_data = ServerMCPConfigCreateInternal(
        name="delete_test",
        type="http",
        url="https://example.com",
        user_id=str(mcp_config_user.id),
    )

    config = await crud_server_mcp_config.create(db=async_session, object=config_data)
    config_id = config.id

    # Soft delete
    await crud_server_mcp_config.update(
        db=async_session,
        object={"is_deleted": True},
        id=config_id,
    )

    # Should not appear in non-deleted queries
    configs = await crud_server_mcp_config.get_multi(
        db=async_session,
        user_id=str(mcp_config_user.id),
        is_deleted=False,
    )

    config_names = [c.name for c in configs.get("data", [])]
    assert "delete_test" not in config_names
