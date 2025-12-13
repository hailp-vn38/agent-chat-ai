import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from src.app.core.db.database import Base, async_get_db
from src.app.core.security import get_password_hash
from src.app.main import app
from src.app.models.user import User
from src.app.schemas.user import UserRead

# Test database configuration
# Use port 5433 to avoid conflict with dev database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db",
)

TEST_REDIS_URL = os.getenv(
    "TEST_REDIS_URL",
    "redis://localhost:6380/0",
)

fake = Faker()


# Function-scoped event loop to avoid "attached to different loop" errors
@pytest.fixture(scope="function")
def event_loop():
    """Create a new event loop for each test function."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a fresh engine for each test function."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def setup_test_db(test_engine):
    """Set up test database - create all tables for each test."""
    async with test_engine.begin() as conn:
        # Drop all tables with CASCADE to handle circular dependencies
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    async with test_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Clean up after test
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


@pytest_asyncio.fixture
async def clean_database(async_session: AsyncSession):
    """Clean all tables after each test to ensure isolation."""
    yield
    # Rollback any uncommitted changes
    await async_session.rollback()

    # Clean tables in order (respecting foreign key constraints)
    tables_to_clean = [
        "agent_template_assignment",
        "template",
        "agent_device",
        "device",
        "agent",
        "user",
    ]

    for table in tables_to_clean:
        try:
            await async_session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            await async_session.commit()
        except Exception:
            await async_session.rollback()


@pytest_asyncio.fixture
async def async_session(
    setup_test_db, test_engine
) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    TestSessionLocal = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""

    async def override_get_db():
        yield async_session

    app.dependency_overrides[async_get_db] = override_get_db

    # httpx AsyncClient sử dụng transport thay vì app parameter
    from httpx import ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        name=fake.name(),
        email=fake.email(),
        hashed_password=get_password_hash("testpassword123"),
        is_superuser=False,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(async_session: AsyncSession) -> User:
    """Create a test superuser."""
    user = User(
        name="Super Admin",
        email="admin@test.com",
        hashed_password=get_password_hash("superpassword123"),
        is_superuser=True,
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for a test user."""
    login_data = {
        "username": test_user.email,  # OAuth2 form uses 'username' field for email
        "password": "testpassword123",
    }

    response = await async_client.post("/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest_asyncio.fixture
async def superuser_headers(async_client: AsyncClient, test_superuser: User) -> dict:
    """Get authentication headers for a test superuser."""
    login_data = {
        "username": test_superuser.email,  # OAuth2 form uses 'username' field for email
        "password": "superpassword123",
    }

    response = await async_client.post("/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.fixture
def sample_user_data():
    """Generate sample user data for tests."""
    return {
        "name": fake.name(),
        "email": fake.email(),
        "password": "TestPassword123!",
    }


@pytest.fixture
def current_user_dict():
    """Mock current user from auth dependency."""
    return {
        "id": str(uuid7()),  # Convert UUID to string
        "email": fake.email(),
        "name": fake.name(),
        "is_superuser": False,
    }


@pytest.fixture
def sample_user_read():
    """Generate sample UserRead schema for tests."""
    return UserRead(
        id=str(uuid7()),  # Convert UUID to string
        name=fake.name(),
        email=fake.email(),
        profile_image_url="https://www.profileimageurl.com",
    )


@pytest_asyncio.fixture
async def test_agent(test_user: User, async_session: AsyncSession):
    """Create a test agent for the test user."""
    from src.app.models.agent import Agent
    from src.app.core.enums import StatusEnum

    # Create agent for test user
    agent = Agent(
        agent_name=f"Test Agent {fake.word()}",
        user_id=test_user.id,
        status=StatusEnum.enabled,
        description="Test agent description",
    )
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_device(test_user: User, async_session: AsyncSession):
    """Create a test device for the test user."""
    from src.app.models.device import Device

    device = Device(
        user_id=test_user.id,
        mac_address=fake.mac_address(),
        device_name=f"Test Device {fake.word()}",
        board="ESP32",
        firmware_version="1.0.0",
        status="online",
    )
    async_session.add(device)
    await async_session.commit()
    await async_session.refresh(device)
    return device


@pytest_asyncio.fixture
async def test_agent_with_device(
    test_user: User, test_device, async_session: AsyncSession
):
    """Create a test agent bound to a device."""
    from src.app.models.agent import Agent
    from src.app.core.enums import StatusEnum

    agent = Agent(
        agent_name=f"Agent with Device {fake.word()}",
        user_id=test_user.id,
        status=StatusEnum.enabled,
        description="Agent with device",
        device_id=test_device.id,
        device_mac_address=test_device.mac_address,
    )
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_agent_template(test_user: User, test_agent, async_session: AsyncSession):
    """Create a test agent template."""
    from src.app.models.agent_template import AgentTemplate

    template = AgentTemplate(
        user_id=test_user.id,
        agent_id=test_agent.id,
        agent_name=test_agent.agent_name,
        prompt="You are a helpful assistant.",
        is_active=True,
        # Provider FK fields are NULL - will use config.yml fallback
        ASR=None,
        LLM=None,
        TTS=None,
    )
    async_session.add(template)
    await async_session.commit()
    await async_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def test_template(test_user: User, async_session: AsyncSession):
    """Create a test template (new shared model)."""
    from src.app.models.template import Template

    template = Template(
        user_id=str(test_user.id),
        name=f"Test Template {fake.word()}",
        prompt="You are a helpful assistant.",
        is_public=False,
    )
    async_session.add(template)
    await async_session.commit()
    await async_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def test_public_template(test_superuser: User, async_session: AsyncSession):
    """Create a public template owned by another user."""
    from src.app.models.template import Template

    template = Template(
        user_id=str(test_superuser.id),
        name=f"Public Template {fake.word()}",
        prompt="Public template prompt.",
        chat_history_conf=5,
        is_public=True,
    )
    async_session.add(template)
    await async_session.commit()
    await async_session.refresh(template)
    return template


@pytest_asyncio.fixture
async def multiple_templates(test_user: User, async_session: AsyncSession):
    """Create multiple test templates for pagination tests."""
    from src.app.models.template import Template

    templates = []
    for i in range(5):
        template = Template(
            user_id=str(test_user.id),
            name=f"Template {i}",
            prompt=f"Prompt {i}",
            chat_history_conf=i,
            is_public=False,
        )
        async_session.add(template)
        templates.append(template)

    await async_session.commit()
    for template in templates:
        await async_session.refresh(template)
    return templates


@pytest_asyncio.fixture
async def test_agent_with_template(
    test_user: User, test_template, async_session: AsyncSession
):
    """Create a test agent with active template."""
    from src.app.models.agent import Agent
    from src.app.models.agent_template_assignment import AgentTemplateAssignment
    from src.app.core.enums import StatusEnum

    agent = Agent(
        agent_name=f"Agent with Template {fake.word()}",
        user_id=test_user.id,
        status=StatusEnum.enabled,
        description="Agent with template",
        active_template_id=str(test_template.id),
    )
    async_session.add(agent)
    await async_session.commit()
    await async_session.refresh(agent)

    # Create assignment
    assignment = AgentTemplateAssignment(
        agent_id=str(agent.id),
        template_id=str(test_template.id),
        is_active=True,
    )
    async_session.add(assignment)
    await async_session.commit()

    return agent


@pytest_asyncio.fixture
async def test_template_with_agents(
    test_user: User, test_template, async_session: AsyncSession
):
    """Create a template with multiple agents assigned."""
    from src.app.models.agent import Agent
    from src.app.models.agent_template_assignment import AgentTemplateAssignment
    from src.app.core.enums import StatusEnum

    agents = []
    for i in range(3):
        agent = Agent(
            agent_name=f"Agent {i} for Template",
            user_id=test_user.id,
            status=StatusEnum.enabled,
            description=f"Agent {i}",
        )
        async_session.add(agent)
        agents.append(agent)

    await async_session.commit()

    for agent in agents:
        await async_session.refresh(agent)
        assignment = AgentTemplateAssignment(
            agent_id=str(agent.id),
            template_id=str(test_template.id),
            is_active=False,
        )
        async_session.add(assignment)

    await async_session.commit()

    return (test_template, agents)


@pytest_asyncio.fixture
async def test_agent_with_assignment(
    test_user: User, test_template, test_agent, async_session: AsyncSession
):
    """Create a test assignment between agent and template."""
    from src.app.models.agent_template_assignment import AgentTemplateAssignment

    assignment = AgentTemplateAssignment(
        agent_id=str(test_agent.id),
        template_id=str(test_template.id),
        is_active=False,
    )
    async_session.add(assignment)
    await async_session.commit()
    await async_session.refresh(assignment)

    return (test_agent, test_template, assignment)


@pytest_asyncio.fixture
async def multiple_agents(test_user: User, async_session: AsyncSession):
    """Create multiple test agents for pagination/filtering tests."""
    from src.app.models.agent import Agent
    from src.app.core.enums import StatusEnum

    agents = []
    for i in range(5):
        agent = Agent(
            agent_name=f"Agent {i}",
            user_id=test_user.id,
            status=StatusEnum.enabled,
            description=f"Description {i}",
            is_deleted=(i == 4),  # Last one is soft-deleted
        )
        async_session.add(agent)
        agents.append(agent)

    await async_session.commit()
    for agent in agents:
        await async_session.refresh(agent)
    return agents


@pytest_asyncio.fixture
async def test_user_tool(test_user: User, async_session: AsyncSession):
    """Create a test user tool configuration."""
    from src.app.models.user_tool import UserTool

    user_tool = UserTool(
        user_id=str(test_user.id),
        tool_name="get_weather",
        name="Test Weather Config",
        config={"api_key": "test-api-key-123", "default_location": "Hanoi"},
        is_active=True,
    )
    async_session.add(user_tool)
    await async_session.commit()
    await async_session.refresh(user_tool)
    return user_tool
