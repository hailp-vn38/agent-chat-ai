"""
Tests for account deletion and restoration endpoints
- DELETE /api/v1/user/me
- POST /api/v1/auth/restore
"""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.user import User


@pytest.mark.asyncio
async def test_delete_account_success(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test successful account deletion"""
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["data"]["message"].lower()
    assert "deleted_at" in data["data"]
    assert "restore_deadline" in data["data"]

    # Verify in database
    await async_session.refresh(test_user)
    assert test_user.is_deleted is True
    assert test_user.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_account_already_deleted(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test deleting already deleted account returns 400"""
    # Delete first time
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Login again to get new token (for testing - in reality user can't login when deleted)
    # For this test, we'll manually restore the account temporarily
    test_user.is_deleted = False
    test_user.deleted_at = None
    await async_session.commit()

    # Get new token
    login_data = {"username": test_user.email, "password": "Testpassword123!"}
    login_response = await client.post("/api/v1/auth/login", data=login_data)
    new_token = login_response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Set back to deleted
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow()
    await async_session.commit()

    # Try to delete again
    response = await client.delete("/api/v1/user/me", headers=new_headers)

    assert response.status_code == 400
    assert "already deleted" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deleted_user_cannot_login(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that deleted user cannot login"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Try to login
    login_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/login", data=login_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_invalidates_tokens(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that tokens are invalidated after deletion"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Try to use old token
    response = await client.get("/api/v1/user/me", headers=user_token_headers)

    # Should be unauthorized
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_unauthenticated(client: AsyncClient):
    """Test deletion without authentication returns 401"""
    response = await client.delete("/api/v1/user/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_restore_account_success(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test successful account restoration"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Restore account
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert "restored successfully" in data["data"]["message"].lower()

    # Verify in database
    await async_session.refresh(test_user)
    assert test_user.is_deleted is False
    assert test_user.deleted_at is None


@pytest.mark.asyncio
async def test_restore_account_wrong_password(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test restore with wrong password returns 401"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Try to restore with wrong password
    restore_data = {"username": test_user.email, "password": "WrongPassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_restore_account_not_deleted(client: AsyncClient, test_user: User):
    """Test restoring non-deleted account returns 400"""
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 400
    assert "not deleted" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_restore_account_expired(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test restoring account after 30-day grace period returns 410"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Manually set deleted_at to 31 days ago
    test_user.deleted_at = datetime.utcnow() - timedelta(days=31)
    await async_session.commit()

    # Try to restore
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 410
    assert "grace period" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_restore_nonexistent_email(client: AsyncClient):
    """Test restore with non-existent email returns 401"""
    restore_data = {"username": "nonexistent@example.com", "password": "Password123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_restore_and_login(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that restored account can login normally"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Restore account
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)
    assert response.status_code == 200
    access_token = response.json()["data"]["access_token"]

    # Use new token to access user data
    new_headers = {"Authorization": f"Bearer {access_token}"}
    response = await client.get("/api/v1/user/me", headers=new_headers)

    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_restore_within_grace_period(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test restoring account within 30-day grace period"""
    # Delete account
    response = await client.delete("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200

    # Set deleted_at to 29 days ago (within grace period)
    test_user.deleted_at = datetime.utcnow() - timedelta(days=29)
    await async_session.commit()

    # Restore should succeed
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)

    assert response.status_code == 200
    assert "access_token" in response.json()["data"]


@pytest.mark.asyncio
async def test_delete_restore_cycle_multiple_times(
    client: AsyncClient, test_user: User, async_session: AsyncSession
):
    """Test multiple delete-restore cycles"""
    for i in range(3):
        # Login
        login_data = {"username": test_user.email, "password": "Testpassword123!"}
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Delete
        delete_response = await client.delete("/api/v1/user/me", headers=headers)
        assert delete_response.status_code == 200

        # Restore
        restore_data = {"username": test_user.email, "password": "Testpassword123!"}
        restore_response = await client.post("/api/v1/auth/restore", data=restore_data)
        assert restore_response.status_code == 200

        # Verify restored
        await async_session.refresh(test_user)
        assert test_user.is_deleted is False
