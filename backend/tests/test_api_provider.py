"""
Integration tests for Provider API endpoints.
"""

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.provider import Provider

fake = Faker()


@pytest_asyncio.fixture
async def test_provider(test_user, async_session: AsyncSession) -> Provider:
    """Create a test provider for API tests."""
    provider = Provider(
        user_id=test_user.id,
        name="Test API Provider",
        category="LLM",
        type="openai",
        config={
            "type": "openai",
            "model_name": "gpt-4",
            "api_key": "sk-test-secret-key",
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
async def multiple_api_providers(
    test_user, async_session: AsyncSession
) -> list[Provider]:
    """Create multiple providers for API tests."""
    providers = []
    configs = [
        ("LLM Provider", "LLM", "openai", {"type": "openai", "api_key": "key1"}),
        ("TTS Provider", "TTS", "edge", {"type": "edge", "voice": "vi-VN-HoaiMyNeural"}),
        ("ASR Provider", "ASR", "deepgram", {"type": "deepgram", "api_key": "key2"}),
    ]

    for name, category, ptype, config in configs:
        provider = Provider(
            user_id=test_user.id,
            name=name,
            category=category,
            type=ptype,
            config=config,
            is_active=True,
        )
        async_session.add(provider)
        providers.append(provider)

    await async_session.commit()
    for p in providers:
        await async_session.refresh(p)
    return providers


class TestProviderSchemaEndpoints:
    """Tests for schema-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_schemas(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas."""
        response = await async_client.get("/api/v1/providers/schemas")

        assert response.status_code == 200
        data = response.json()
        assert "LLM" in data
        assert "TTS" in data
        assert "ASR" in data
        assert "openai" in data["LLM"]
        assert "edge" in data["TTS"]

    @pytest.mark.asyncio
    async def test_get_schema_categories(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/categories with full schema data."""
        response = await async_client.get("/api/v1/providers/schemas/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "data" in data
        assert "LLM" in data["categories"]
        assert "TTS" in data["categories"]
        assert "ASR" in data["categories"]
        # Verify data contains schemas
        assert "LLM" in data["data"]
        assert "openai" in data["data"]["LLM"]

    @pytest.mark.asyncio
    async def test_get_category_schemas(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/{category}."""
        response = await async_client.get("/api/v1/providers/schemas/LLM")

        assert response.status_code == 200
        data = response.json()
        assert "openai" in data
        assert "gemini" in data
        assert data["openai"]["label"] == "OpenAI Compatible"

    @pytest.mark.asyncio
    async def test_get_category_schemas_not_found(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/{category} with invalid category."""
        response = await async_client.get("/api/v1/providers/schemas/INVALID")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_provider_types(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/{category}/types."""
        response = await async_client.get("/api/v1/providers/schemas/TTS/types")

        assert response.status_code == 200
        types = response.json()
        assert "edge" in types
        assert "google" in types
        assert "deepgram" in types

    @pytest.mark.asyncio
    async def test_get_single_schema(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/{category}/{type}."""
        response = await async_client.get("/api/v1/providers/schemas/LLM/openai")

        assert response.status_code == 200
        schema = response.json()
        assert schema["label"] == "OpenAI Compatible"
        assert "fields" in schema
        assert len(schema["fields"]) > 0

        # Check field structure
        field_names = [f["name"] for f in schema["fields"]]
        assert "model_name" in field_names
        assert "api_key" in field_names
        assert "temperature" in field_names

    @pytest.mark.asyncio
    async def test_get_single_schema_not_found(self, async_client: AsyncClient):
        """Test GET /api/v1/providers/schemas/{category}/{type} not found."""
        response = await async_client.get("/api/v1/providers/schemas/LLM/invalid_type")

        assert response.status_code == 404


class TestProviderValidationEndpoints:
    """Tests for validation endpoints."""

    @pytest.mark.asyncio
    async def test_validate_valid_config(self, async_client: AsyncClient):
        """Test POST /api/v1/providers/validate with valid config."""
        response = await async_client.post(
            "/api/v1/providers/validate",
            json={
                "category": "LLM",
                "type": "openai",
                "config": {
                    "model_name": "gpt-4",
                    "api_key": "sk-test-key",
                    "temperature": 0.5,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["normalized_config"] is not None
        assert data["normalized_config"]["temperature"] == 0.5
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_invalid_config_missing_required(
        self, async_client: AsyncClient
    ):
        """Test validation with missing required fields."""
        response = await async_client.post(
            "/api/v1/providers/validate",
            json={
                "category": "LLM",
                "type": "openai",
                "config": {
                    "temperature": 0.5,
                    # missing model_name and api_key
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["normalized_config"] is None
        assert len(data["errors"]) >= 2

    @pytest.mark.asyncio
    async def test_validate_invalid_config_out_of_range(
        self, async_client: AsyncClient
    ):
        """Test validation with out of range values."""
        response = await async_client.post(
            "/api/v1/providers/validate",
            json={
                "category": "LLM",
                "type": "openai",
                "config": {
                    "model_name": "gpt-4",
                    "api_key": "sk-test",
                    "temperature": 5.0,  # max is 2
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any("temperature" in e for e in data["errors"])


class TestProviderCRUDEndpoints:
    """Tests for CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_providers_unauthorized(self, async_client: AsyncClient):
        """Test listing providers without authentication."""
        response = await async_client.get("/api/v1/providers")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_providers_empty(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test listing providers when none exist."""
        response = await async_client.get("/api/v1/providers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["data"] == []
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_providers(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_api_providers: list[Provider],
    ):
        """Test listing providers."""
        response = await async_client.get("/api/v1/providers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["data"]) == 3

    @pytest.mark.asyncio
    async def test_list_providers_by_category(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_api_providers: list[Provider],
    ):
        """Test listing providers filtered by category."""
        response = await async_client.get(
            "/api/v1/providers?category=LLM", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["data"][0]["category"] == "LLM"

    @pytest.mark.asyncio
    async def test_list_providers_secrets_masked(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test that secret fields are masked in list response."""
        response = await async_client.get("/api/v1/providers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        # API key should be masked
        assert data["data"][0]["config"]["api_key"] == "***"

    @pytest.mark.asyncio
    async def test_create_provider(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating a new provider."""
        response = await async_client.post(
            "/api/v1/providers",
            headers=auth_headers,
            json={
                "name": "My New Provider",
                "category": "LLM",
                "type": "openai",
                "config": {
                    "model_name": "gpt-4",
                    "api_key": "sk-new-key",
                },
                "is_active": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My New Provider"
        assert data["category"] == "LLM"
        assert data["type"] == "openai"
        # Secret masked
        assert data["config"]["api_key"] == "***"
        # Defaults applied
        assert data["config"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_create_provider_invalid_config(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating provider with invalid config."""
        response = await async_client.post(
            "/api/v1/providers",
            headers=auth_headers,
            json={
                "name": "Invalid Provider",
                "category": "LLM",
                "type": "openai",
                "config": {
                    # missing required fields
                    "temperature": 0.5,
                },
                "is_active": True,
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "errors" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_provider(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test getting a single provider."""
        response = await async_client.get(
            f"/api/v1/providers/{test_provider.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_provider.id
        assert data["name"] == test_provider.name
        # Secret masked
        assert data["config"]["api_key"] == "***"

    @pytest.mark.asyncio
    async def test_get_provider_not_found(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent provider."""
        response = await async_client.get(
            "/api/v1/providers/non-existent-id", headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_provider(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test updating a provider."""
        response = await async_client.put(
            f"/api/v1/providers/{test_provider.id}",
            headers=auth_headers,
            json={
                "name": "Updated Provider",
                "is_active": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Provider"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_provider_config(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test updating provider config."""
        response = await async_client.put(
            f"/api/v1/providers/{test_provider.id}",
            headers=auth_headers,
            json={
                "config": {
                    "model_name": "gpt-4-turbo",
                    "api_key": "sk-new-key",
                    "temperature": 0.3,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["model_name"] == "gpt-4-turbo"
        assert data["config"]["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_update_provider_invalid_config(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test updating provider with invalid config."""
        response = await async_client.put(
            f"/api/v1/providers/{test_provider.id}",
            headers=auth_headers,
            json={
                "config": {
                    "model_name": "gpt-4",
                    "api_key": "sk-key",
                    "temperature": 10.0,  # invalid
                },
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_provider(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_provider: Provider,
    ):
        """Test deleting a provider."""
        response = await async_client.delete(
            f"/api/v1/providers/{test_provider.id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify it's deleted
        response = await async_client.get(
            f"/api/v1/providers/{test_provider.id}", headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_provider_not_found(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test deleting non-existent provider."""
        response = await async_client.delete(
            "/api/v1/providers/non-existent-id", headers=auth_headers
        )

        assert response.status_code == 404


class TestProviderPagination:
    """Tests for pagination."""

    @pytest.mark.asyncio
    async def test_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        multiple_api_providers: list[Provider],
    ):
        """Test provider list pagination."""
        # First page
        response = await async_client.get(
            "/api/v1/providers?page=1&page_size=2", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2

        # Second page
        response = await async_client.get(
            "/api/v1/providers?page=2&page_size=2", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

