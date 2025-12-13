"""
Tests for user profile update endpoint (PATCH /api/v1/user/me)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.user import User


@pytest.mark.asyncio
async def test_update_user_name(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test updating user name"""
    update_data = {"name": "Updated Name"}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_update_user_email(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test updating user email"""
    new_email = "newemail@example.com"
    update_data = {"email": new_email}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == new_email
    assert data["id"] == str(test_user.id)

    # Verify in database
    await async_session.refresh(test_user)
    assert test_user.email == new_email


@pytest.mark.asyncio
async def test_update_user_profile_image_url(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test updating profile image URL"""
    new_url = "https://example.com/new-image.jpg"
    update_data = {"profile_image_url": new_url}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["profile_image_url"] == new_url


@pytest.mark.asyncio
async def test_update_multiple_fields(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test updating multiple fields at once"""
    update_data = {
        "name": "New Name",
        "email": "newmail@test.com",
        "profile_image_url": "https://example.com/avatar.png",
    }

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["email"] == "newmail@test.com"
    assert data["profile_image_url"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_update_email_duplicate(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    user_token_headers: dict[str, str],
):
    """Test updating to an already existing email returns 409"""
    # Try to update to superuser's email
    update_data = {"email": test_superuser.email}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_partial_fields(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test partial update (only one field)"""
    original_email = test_user.email
    update_data = {"name": "Only Name Changed"}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Only Name Changed"
    assert data["email"] == original_email  # Email unchanged


@pytest.mark.asyncio
async def test_update_empty_body(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test update with empty body returns current user data"""
    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json={}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email
    assert data["name"] == test_user.name


@pytest.mark.asyncio
async def test_update_invalid_email_format(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test updating with invalid email format returns 422"""
    update_data = {"email": "not-an-email"}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_unauthenticated(client: AsyncClient):
    """Test update without authentication returns 401"""
    update_data = {"name": "New Name"}

    response = await client.patch("/api/v1/user/me", json=update_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_invalid_token(client: AsyncClient):
    """Test update with invalid token returns 401"""
    update_data = {"name": "New Name"}

    response = await client.patch(
        "/api/v1/user/me",
        headers={"Authorization": "Bearer invalid_token"},
        json=update_data,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_name_too_short(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test updating name with less than 2 characters returns 422"""
    update_data = {"name": "A"}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_name_too_long(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test updating name with more than 30 characters returns 422"""
    update_data = {"name": "A" * 31}

    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )

    assert response.status_code == 422
