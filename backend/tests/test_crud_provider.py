"""
Unit tests for Provider CRUD operations.
"""

import pytest
import pytest_asyncio
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.crud.crud_provider import crud_provider
from src.app.models.provider import Provider
from src.app.schemas.provider import (
    ProviderCreateInternal,
    ProviderRead,
    ProviderUpdateInternal,
)

fake = Faker()


@pytest_asyncio.fixture
async def test_provider(test_user, async_session: AsyncSession) -> Provider:
    """Create a test provider."""
    provider = Provider(
        user_id=test_user.id,
        name="Test LLM Provider",
        category="LLM",
        type="openai",
        config={
            "type": "openai",
            "model_name": "gpt-4",
            "api_key": "sk-test-key",
            "temperature": 0.7,
            "max_tokens": 4000,
        },
        is_active=True,
    )
    async_session.add(provider)
    await async_session.commit()
    await async_session.refresh(provider)
    return provider


@pytest_asyncio.fixture
async def multiple_providers(test_user, async_session: AsyncSession) -> list[Provider]:
    """Create multiple test providers."""
    providers = []

    # LLM providers
    for i in range(2):
        provider = Provider(
            user_id=test_user.id,
            name=f"LLM Provider {i}",
            category="LLM",
            type="openai" if i == 0 else "gemini",
            config={"type": "openai" if i == 0 else "gemini", "api_key": f"key-{i}"},
            is_active=True,
        )
        async_session.add(provider)
        providers.append(provider)

    # TTS providers
    for i in range(2):
        provider = Provider(
            user_id=test_user.id,
            name=f"TTS Provider {i}",
            category="TTS",
            type="edge" if i == 0 else "google",
            config={"type": "edge" if i == 0 else "google", "voice": "test-voice"},
            is_active=i == 0,  # Second one is inactive
        )
        async_session.add(provider)
        providers.append(provider)

    # Deleted provider
    deleted_provider = Provider(
        user_id=test_user.id,
        name="Deleted Provider",
        category="ASR",
        type="deepgram",
        config={"type": "deepgram", "api_key": "deleted-key"},
        is_active=True,
        is_deleted=True,
    )
    async_session.add(deleted_provider)
    providers.append(deleted_provider)

    await async_session.commit()
    for p in providers:
        await async_session.refresh(p)
    return providers


class TestProviderCRUD:
    """Tests for Provider CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_provider(self, test_user, async_session: AsyncSession):
        """Test creating a new provider."""
        provider_data = ProviderCreateInternal(
            user_id=test_user.id,
            name="New OpenAI Provider",
            category="LLM",
            type="openai",
            config={
                "type": "openai",
                "model_name": "gpt-4",
                "api_key": "sk-new-key",
            },
            is_active=True,
        )

        created = await crud_provider.create(db=async_session, object=provider_data)

        assert created is not None
        assert created.id is not None
        assert created.name == "New OpenAI Provider"
        assert created.category == "LLM"
        assert created.type == "openai"
        assert created.config["api_key"] == "sk-new-key"
        assert created.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_get_provider_by_id(
        self, test_provider: Provider, async_session: AsyncSession
    ):
        """Test getting a provider by ID."""
        provider = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert provider is not None
        assert provider.id == test_provider.id
        assert provider.name == test_provider.name

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, async_session: AsyncSession):
        """Test getting a non-existent provider returns None."""
        provider = await crud_provider.get(
            db=async_session,
            id="non-existent-id",
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert provider is None

    @pytest.mark.asyncio
    async def test_get_provider_with_user_filter(
        self, test_provider: Provider, test_user, async_session: AsyncSession
    ):
        """Test getting a provider with user_id filter."""
        # Should find with correct user
        provider = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            user_id=test_user.id,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )
        assert provider is not None

        # Should not find with wrong user
        provider = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            user_id="wrong-user-id",
            schema_to_select=ProviderRead,
            return_as_model=True,
        )
        assert provider is None

    @pytest.mark.asyncio
    async def test_get_multi_providers(
        self, multiple_providers, test_user, async_session: AsyncSession
    ):
        """Test getting multiple providers with pagination."""
        result = await crud_provider.get_multi(
            db=async_session,
            user_id=test_user.id,
            is_deleted=False,
            offset=0,
            limit=10,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        # Should return 4 providers (excluding deleted one)
        assert result["total_count"] == 4
        assert len(result["data"]) == 4

    @pytest.mark.asyncio
    async def test_get_multi_providers_by_category(
        self, multiple_providers, test_user, async_session: AsyncSession
    ):
        """Test filtering providers by category."""
        result = await crud_provider.get_multi(
            db=async_session,
            user_id=test_user.id,
            category="LLM",
            is_deleted=False,
            offset=0,
            limit=10,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert result["total_count"] == 2
        for provider in result["data"]:
            assert provider.category == "LLM"

    @pytest.mark.asyncio
    async def test_get_multi_providers_pagination(
        self, multiple_providers, test_user, async_session: AsyncSession
    ):
        """Test pagination of providers."""
        # First page
        result1 = await crud_provider.get_multi(
            db=async_session,
            user_id=test_user.id,
            is_deleted=False,
            offset=0,
            limit=2,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert len(result1["data"]) == 2
        assert result1["total_count"] == 4

        # Second page
        result2 = await crud_provider.get_multi(
            db=async_session,
            user_id=test_user.id,
            is_deleted=False,
            offset=2,
            limit=2,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert len(result2["data"]) == 2

        # Different providers
        ids1 = {p.id for p in result1["data"]}
        ids2 = {p.id for p in result2["data"]}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_update_provider(
        self, test_provider: Provider, async_session: AsyncSession
    ):
        """Test updating a provider."""
        from datetime import datetime, timezone

        update_data = ProviderUpdateInternal(
            name="Updated Provider Name",
            config={
                "type": "openai",
                "model_name": "gpt-4-turbo",
                "api_key": "sk-updated-key",
            },
            is_active=False,
            updated_at=datetime.now(timezone.utc),
        )

        await crud_provider.update(
            db=async_session,
            object=update_data,
            id=test_provider.id,
        )

        # Fetch updated provider
        updated = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )

        assert updated.name == "Updated Provider Name"
        assert updated.config["model_name"] == "gpt-4-turbo"
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_delete_provider_soft(
        self, test_provider: Provider, async_session: AsyncSession
    ):
        """Test soft deleting a provider."""
        # FastCRUD automatically does soft delete when model has is_deleted column
        await crud_provider.delete(
            db=async_session,
            id=test_provider.id,
        )

        # Should not find with is_deleted=False filter
        provider = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            is_deleted=False,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )
        assert provider is None

        # Should find without filter (soft deleted)
        provider = await crud_provider.get(
            db=async_session,
            id=test_provider.id,
            schema_to_select=ProviderRead,
            return_as_model=True,
        )
        assert provider is not None
        assert provider.is_deleted is True

    @pytest.mark.asyncio
    async def test_create_multiple_providers_same_user(
        self, test_user, async_session: AsyncSession
    ):
        """Test creating multiple providers for the same user."""
        for i in range(3):
            provider_data = ProviderCreateInternal(
                user_id=test_user.id,
                name=f"Provider {i}",
                category="LLM",
                type="openai",
                config={"type": "openai", "api_key": f"key-{i}"},
                is_active=True,
            )
            await crud_provider.create(db=async_session, object=provider_data)

        result = await crud_provider.get_multi(
            db=async_session,
            user_id=test_user.id,
            is_deleted=False,
        )

        assert result["total_count"] == 3

