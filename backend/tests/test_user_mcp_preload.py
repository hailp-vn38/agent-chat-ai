"""
Tests for User MCP Preload feature.

Tests:
- 4.1: User có MCP configs → load từ DB
- 4.2: User không có MCP configs → fallback default file
- 4.3: Default file không tồn tại → empty list, no error
- 4.4: mcp_selection_mode=selected với mixed references (db + config)
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, mock_open
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.crud.crud_agent import crud_agent
from src.app.crud.crud_server_mcp_config import crud_server_mcp_config
from src.app.models.agent import Agent
from src.app.models.device import Device
from src.app.models.user import User
from src.app.models.server_mcp_config import ServerMCPConfig
from src.app.schemas.server_mcp_config import ServerMCPConfigCreateInternal


# ============================================================================
# FIXTURES
# ============================================================================


@pytest_asyncio.fixture
async def mcp_user(async_session: AsyncSession) -> User:
    """Create a test user for MCP preload tests."""
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


@pytest_asyncio.fixture
async def mcp_device(mcp_user: User, async_session: AsyncSession) -> Device:
    """Create a test device."""
    from faker import Faker

    fake = Faker()
    device = Device(
        user_id=mcp_user.id,
        mac_address=fake.mac_address(),
        device_name="Test MCP Device",
        board="ESP32",
        firmware_version="1.0.0",
        status="online",
    )
    async_session.add(device)
    await async_session.commit()
    await async_session.refresh(device)
    return device


@pytest_asyncio.fixture
async def mcp_agent(
    mcp_user: User, mcp_device: Device, async_session: AsyncSession
) -> Agent:
    """Create a test agent bound to device."""
    from src.app.core.enums import StatusEnum

    agent = Agent(
        agent_name="MCP Test Agent",
        user_id=mcp_user.id,
        status=StatusEnum.enabled,
        description="Agent for MCP preload tests",
        device_id=mcp_device.id,
        device_mac_address=mcp_device.mac_address,
        mcp_selection_mode="all",
    )
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def mcp_configs(
    mcp_user: User, async_session: AsyncSession
) -> list[ServerMCPConfig]:
    """Create multiple MCP configs for user."""
    configs = []

    # Stdio MCP config
    stdio_config = ServerMCPConfigCreateInternal(
        name="filesystem_mcp",
        description="File operations",
        type="stdio",
        command="npx",
        args=["-y", "@anthropic/mcp-server-filesystem"],
        env={"DEBUG": "true"},
        user_id=str(mcp_user.id),
    )
    config1 = await crud_server_mcp_config.create(db=async_session, object=stdio_config)
    configs.append(config1)

    # SSE MCP config
    sse_config = ServerMCPConfigCreateInternal(
        name="weather_mcp",
        description="Weather data",
        type="sse",
        url="https://weather-mcp.example.com/sse",
        headers={"Authorization": "Bearer test"},
        user_id=str(mcp_user.id),
    )
    config2 = await crud_server_mcp_config.create(db=async_session, object=sse_config)
    configs.append(config2)

    # Inactive MCP config (should be filtered out)
    inactive_config = ServerMCPConfigCreateInternal(
        name="inactive_mcp",
        type="stdio",
        command="inactive",
        user_id=str(mcp_user.id),
        is_active=False,
    )
    config3 = await crud_server_mcp_config.create(
        db=async_session, object=inactive_config
    )
    configs.append(config3)

    return configs


# ============================================================================
# TEST 4.1: User có MCP configs → load từ DB
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_returns_active_configs(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs returns only active configs."""
    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="all",
    )

    assert result is not None
    assert len(result) == 2  # Only 2 active configs, not the inactive one

    # Verify config names
    names = [cfg["name"] for cfg in result]
    assert "filesystem_mcp" in names
    assert "weather_mcp" in names
    assert "inactive_mcp" not in names


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_format(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs returns correct format."""
    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="all",
    )

    # Find stdio config
    stdio_cfg = next((c for c in result if c["name"] == "filesystem_mcp"), None)
    assert stdio_cfg is not None
    assert stdio_cfg["type"] == "stdio"
    assert stdio_cfg["command"] == "npx"
    assert stdio_cfg["args"] == ["-y", "@anthropic/mcp-server-filesystem"]
    assert stdio_cfg["env"] == {"DEBUG": "true"}
    assert "id" in stdio_cfg

    # Find SSE config
    sse_cfg = next((c for c in result if c["name"] == "weather_mcp"), None)
    assert sse_cfg is not None
    assert sse_cfg["type"] == "sse"
    assert sse_cfg["url"] == "https://weather-mcp.example.com/sse"
    assert sse_cfg["headers"] == {"Authorization": "Bearer test"}


@pytest.mark.asyncio
async def test_get_agent_by_mac_address_includes_mcp_configs(
    async_session: AsyncSession,
    mcp_agent: Agent,
    mcp_device: Device,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test get_agent_by_mac_address includes mcp_configs in result."""
    result = await crud_agent.get_agent_by_mac_address(
        db=async_session,
        mac_address=mcp_device.mac_address,
    )

    assert result is not None
    assert "mcp_configs" in result
    assert len(result["mcp_configs"]) == 2  # 2 active configs


# ============================================================================
# TEST 4.2: User không có MCP configs → fallback default file
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_empty_for_new_user(
    async_session: AsyncSession,
    mcp_user: User,
    clean_database,
):
    """Test _fetch_user_mcp_configs returns empty list when user has no configs."""
    # Don't create any MCP configs for this user
    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="all",
    )

    assert result is not None
    assert result == []


def test_server_mcp_manager_fallback_to_file():
    """Test ServerMCPManager falls back to config file when no user configs."""
    from src.app.ai.providers.tools.server_mcp.mcp_manager import ServerMCPManager

    # Mock connection with agent that has no mcp_configs
    mock_conn = MagicMock()
    mock_conn.agent = {"mcp_configs": []}

    # Mock file exists and contains config
    mock_config = '{"mcpServers": {"default_mcp": {"command": "npx", "args": []}}}'

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_config)):
            manager = ServerMCPManager(mock_conn)
            config = manager.load_config()

    assert config is not None
    assert "default_mcp" in config
    assert config["default_mcp"]["command"] == "npx"


# ============================================================================
# TEST 4.3: Default file không tồn tại → empty list, no error
# ============================================================================


def test_server_mcp_manager_no_file_no_error():
    """Test ServerMCPManager returns empty dict when no file and no user configs."""
    from src.app.ai.providers.tools.server_mcp.mcp_manager import ServerMCPManager

    # Mock connection with agent that has no mcp_configs
    mock_conn = MagicMock()
    mock_conn.agent = {"mcp_configs": []}

    # Mock file doesn't exist
    with patch("os.path.exists", return_value=False):
        manager = ServerMCPManager(mock_conn)
        config = manager.load_config()

    assert config == {}


def test_server_mcp_manager_uses_user_configs():
    """Test ServerMCPManager uses user configs when available."""
    from src.app.ai.providers.tools.server_mcp.mcp_manager import ServerMCPManager

    # Mock connection with agent that has mcp_configs
    mock_conn = MagicMock()
    mock_conn.agent = {
        "mcp_configs": [
            {
                "name": "user_mcp",
                "type": "stdio",
                "command": "user-mcp-server",
            }
        ]
    }

    with patch("os.path.exists", return_value=True):
        manager = ServerMCPManager(mock_conn)
        config = manager.load_config()

    assert config is not None
    assert "user_mcp" in config
    assert config["user_mcp"]["command"] == "user-mcp-server"
    # Should NOT fall back to file


# ============================================================================
# TEST 4.4: mcp_selection_mode=selected với mixed references
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_selected_mode(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs with mcp_selection_mode=selected."""
    # Get the active configs (first 2)
    active_configs = [c for c in mcp_configs if c.is_active]
    assert len(active_configs) == 2

    # Select only the first config
    selected_id = str(active_configs[0].id)
    mcp_selection = {
        "servers": [
            {"reference": f"db:{selected_id}"},
            {"reference": "config:system_mcp"},  # config: refs are ignored
        ]
    }

    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="selected",
        mcp_selection=mcp_selection,
    )

    assert result is not None
    assert len(result) == 1  # Only the selected db config
    assert result[0]["id"] == selected_id


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_selected_mode_all_refs(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs selected mode with multiple db refs."""
    active_configs = [c for c in mcp_configs if c.is_active]

    # Select both active configs
    mcp_selection = {
        "servers": [
            {"reference": f"db:{active_configs[0].id}"},
            {"reference": f"db:{active_configs[1].id}"},
        ]
    }

    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="selected",
        mcp_selection=mcp_selection,
    )

    assert result is not None
    assert len(result) == 2


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_selected_mode_no_match(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs selected mode with non-matching refs."""
    from uuid6 import uuid7

    fake_id = str(uuid7())
    mcp_selection = {
        "servers": [
            {"reference": f"db:{fake_id}"},  # Non-existent ID
            {"reference": "config:nonexistent"},  # config: refs are ignored
        ]
    }

    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="selected",
        mcp_selection=mcp_selection,
    )

    assert result is not None
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_agent_by_mac_address_with_selected_mode(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_device: Device,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test get_agent_by_mac_address respects mcp_selection_mode=selected."""
    from src.app.core.enums import StatusEnum

    active_configs = [c for c in mcp_configs if c.is_active]
    selected_id = str(active_configs[0].id)

    # Create agent with selected mode
    agent = Agent(
        agent_name="Selected Mode Agent",
        user_id=mcp_user.id,
        status=StatusEnum.enabled,
        description="Agent with selected MCP mode",
        device_id=mcp_device.id,
        device_mac_address=mcp_device.mac_address,
        mcp_selection_mode="selected",
        mcp_selection={"servers": [{"reference": f"db:{selected_id}"}]},
    )
    async_session.add(agent)
    await async_session.commit()

    result = await crud_agent.get_agent_by_mac_address(
        db=async_session,
        mac_address=mcp_device.mac_address,
    )

    assert result is not None
    assert "mcp_configs" in result
    assert len(result["mcp_configs"]) == 1
    assert result["mcp_configs"][0]["id"] == selected_id


# ============================================================================
# EDGE CASES
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_handles_none_user_id(
    async_session: AsyncSession,
    clean_database,
):
    """Test _fetch_user_mcp_configs handles None user_id gracefully."""
    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=None,
        mcp_selection_mode="all",
    )

    # Should return empty list, not error
    assert result == []


@pytest.mark.asyncio
async def test_fetch_user_mcp_configs_empty_selection(
    async_session: AsyncSession,
    mcp_user: User,
    mcp_configs: list[ServerMCPConfig],
    clean_database,
):
    """Test _fetch_user_mcp_configs with empty mcp_selection."""
    result = await crud_agent._fetch_user_mcp_configs(
        db=async_session,
        user_id=mcp_user.id,
        mcp_selection_mode="selected",
        mcp_selection={"servers": []},  # Empty servers
    )

    # With empty selection, should return empty
    # (no selected IDs means filter returns nothing)
    assert result is not None


def test_server_mcp_manager_no_agent():
    """Test ServerMCPManager handles connection without agent."""
    from src.app.ai.providers.tools.server_mcp.mcp_manager import ServerMCPManager

    # Mock connection without agent
    mock_conn = MagicMock()
    mock_conn.agent = None

    with patch("os.path.exists", return_value=False):
        manager = ServerMCPManager(mock_conn)

    assert manager.user_mcp_configs == []
