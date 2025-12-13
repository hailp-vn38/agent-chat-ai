"""
Tests for password change endpoint (PUT /api/v1/user/me/password)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.security import verify_password
from src.app.models.user import User


@pytest.mark.asyncio
async def test_change_password_success(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test successful password change"""
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": "NewPassword456!",
    }

    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "password updated successfully" in data["data"]["message"].lower()

    # Verify new password in database
    await async_session.refresh(test_user)
    assert verify_password("NewPassword456!", test_user.hashed_password)


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test password change with wrong current password returns 401"""
    password_data = {
        "current_password": "WrongPassword123!",
        "new_password": "NewPassword456!",
    }

    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_weak_new_password(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test password change with weak new password returns 422"""
    weak_passwords = [
        "short",  # Too short
        "nouppercase123!",  # No uppercase
        "NOLOWERCASE123!",  # No lowercase
        "NoNumbers!",  # No numbers
        "NoSpecialChar123",  # No special characters
    ]

    for weak_password in weak_passwords:
        password_data = {
            "current_password": "Testpassword123!",
            "new_password": weak_password,
        }

        response = await client.put(
            "/api/v1/user/me/password", headers=user_token_headers, json=password_data
        )

        assert (
            response.status_code == 422
        ), f"Weak password '{weak_password}' should be rejected"


@pytest.mark.asyncio
async def test_change_password_invalidates_tokens(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that old tokens are invalid after password change"""
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": "NewPassword456!",
    }

    # Change password
    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )
    assert response.status_code == 200

    # Try to use old token
    response = await client.get("/api/v1/user/me", headers=user_token_headers)

    # Token should be blacklisted
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_can_login_with_new(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that user can login with new password after change"""
    new_password = "NewPassword456!"
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": new_password,
    }

    # Change password
    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )
    assert response.status_code == 200

    # Login with new password
    login_data = {"username": test_user.email, "password": new_password}
    response = await client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_change_password_cannot_login_with_old(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that user cannot login with old password after change"""
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": "NewPassword456!",
    }

    # Change password
    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )
    assert response.status_code == 200

    # Try to login with old password
    login_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_unauthenticated(client: AsyncClient):
    """Test password change without authentication returns 401"""
    password_data = {
        "current_password": "OldPassword123!",
        "new_password": "NewPassword456!",
    }

    response = await client.put("/api/v1/user/me/password", json=password_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_missing_current(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test password change without current_password returns 422"""
    password_data = {"new_password": "NewPassword456!"}

    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_missing_new(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test password change without new_password returns 422"""
    password_data = {"current_password": "Testpassword123!"}

    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_same_as_current(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test changing to the same password (should succeed)"""
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": "Testpassword123!",
    }

    response = await client.put(
        "/api/v1/user/me/password", headers=user_token_headers, json=password_data
    )

    # Should succeed (no validation against same password)
    assert response.status_code == 200
