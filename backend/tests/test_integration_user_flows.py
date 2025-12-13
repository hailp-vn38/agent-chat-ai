"""
Integration tests for complete user management workflows
Tests full end-to-end flows combining multiple endpoints
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.user import User


@pytest.mark.asyncio
async def test_full_registration_to_profile_update_flow(
    client: AsyncClient, async_session: AsyncSession
):
    """Test complete flow: register -> login -> update profile"""
    # 1. Register new user
    register_data = {
        "name": "Integration Test User",
        "email": "integration@test.com",
        "password": "TestPassword123!",
    }
    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # 2. Login
    login_data = {"username": "integration@test.com", "password": "TestPassword123!"}
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Get profile
    response = await client.get("/api/v1/user/me", headers=headers)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "integration@test.com"
    assert user_data["name"] == "Integration Test User"

    # 4. Update profile
    update_data = {"name": "Updated Name"}
    response = await client.patch("/api/v1/user/me", headers=headers, json=update_data)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"

    # 5. Verify update persisted
    response = await client.get("/api/v1/user/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_full_delete_and_restore_flow(client: AsyncClient, test_user: User):
    """Test complete flow: login -> delete -> restore -> login again"""
    # 1. Login
    login_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Delete account
    response = await client.delete("/api/v1/user/me", headers=headers)
    assert response.status_code == 200
    delete_data = response.json()["data"]
    assert "deleted_at" in delete_data
    assert "restore_deadline" in delete_data

    # 3. Verify cannot login with deleted account
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 401

    # 4. Verify old token is invalid
    response = await client.get("/api/v1/user/me", headers=headers)
    assert response.status_code == 401

    # 5. Restore account
    restore_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/restore", data=restore_data)
    assert response.status_code == 200
    new_access_token = response.json()["data"]["access_token"]
    new_headers = {"Authorization": f"Bearer {new_access_token}"}

    # 6. Verify can access account with new token
    response = await client.get("/api/v1/user/me", headers=new_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email

    # 7. Verify can login normally
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_password_change_and_relogin_flow(client: AsyncClient, test_user: User):
    """Test complete flow: login -> change password -> re-login with new password"""
    # 1. Login with old password
    login_data = {"username": test_user.email, "password": "Testpassword123!"}
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    old_token = response.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # 2. Change password
    password_data = {
        "current_password": "Testpassword123!",
        "new_password": "NewSecurePassword456!",
    }
    response = await client.put(
        "/api/v1/user/me/password", headers=old_headers, json=password_data
    )
    assert response.status_code == 200

    # 3. Verify old token is invalid
    response = await client.get("/api/v1/user/me", headers=old_headers)
    assert response.status_code == 401

    # 4. Verify cannot login with old password
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 401

    # 5. Login with new password
    new_login_data = {"username": test_user.email, "password": "NewSecurePassword456!"}
    response = await client.post("/api/v1/auth/login", data=new_login_data)
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 6. Verify can access account
    response = await client.get("/api/v1/user/me", headers=new_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_upload_image_and_verify_url_flow(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test complete flow: upload image -> verify URL updated -> access profile"""
    # Import here to avoid issues if PIL not installed
    from io import BytesIO
    from PIL import Image

    # 1. Create test image
    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    # 2. Upload image
    files = {"file": ("profile.jpg", img_bytes.read(), "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )
    assert response.status_code == 200
    upload_data = response.json()["data"]
    assert "profile_image_url" in upload_data
    image_url = upload_data["profile_image_url"]

    # 3. Verify URL is in profile
    response = await client.get("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200
    profile_data = response.json()
    assert profile_data["profile_image_url"] == image_url

    # 4. Update profile (should preserve image URL)
    update_data = {"name": "Updated Name"}
    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json=update_data
    )
    assert response.status_code == 200
    assert response.json()["profile_image_url"] == image_url


@pytest.mark.asyncio
async def test_complete_user_lifecycle(
    client: AsyncClient, async_session: AsyncSession
):
    """Test complete user lifecycle: register -> update -> change password -> delete -> restore"""
    email = "lifecycle@test.com"
    original_password = "OriginalPass123!"
    new_password = "NewPass456!"

    # 1. Register
    register_data = {
        "name": "Lifecycle User",
        "email": email,
        "password": original_password,
    }
    response = await client.post("/api/v1/auth/register", json=register_data)
    assert response.status_code == 201

    # 2. Login
    login_data = {"username": email, "password": original_password}
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    token1 = response.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # 3. Update profile
    response = await client.patch(
        "/api/v1/user/me", headers=headers1, json={"name": "Updated Lifecycle User"}
    )
    assert response.status_code == 200

    # 4. Change password
    response = await client.put(
        "/api/v1/user/me/password",
        headers=headers1,
        json={"current_password": original_password, "new_password": new_password},
    )
    assert response.status_code == 200

    # 5. Login with new password
    login_data = {"username": email, "password": new_password}
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    token2 = response.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # 6. Delete account
    response = await client.delete("/api/v1/user/me", headers=headers2)
    assert response.status_code == 200

    # 7. Verify cannot login
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 401

    # 8. Restore account
    restore_data = {"username": email, "password": new_password}
    response = await client.post("/api/v1/auth/restore", data=restore_data)
    assert response.status_code == 200
    token3 = response.json()["data"]["access_token"]
    headers3 = {"Authorization": f"Bearer {token3}"}

    # 9. Verify profile is intact
    response = await client.get("/api/v1/user/me", headers=headers3)
    assert response.status_code == 200
    profile = response.json()
    assert profile["email"] == email
    assert profile["name"] == "Updated Lifecycle User"

    # 10. Login normally works
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_multiple_profile_operations_in_sequence(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test multiple profile operations in sequence"""
    # 1. Update name
    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json={"name": "Name 1"}
    )
    assert response.status_code == 200

    # 2. Update email
    response = await client.patch(
        "/api/v1/user/me",
        headers=user_token_headers,
        json={"email": "newemail@test.com"},
    )
    assert response.status_code == 200

    # 3. Update profile image URL
    response = await client.patch(
        "/api/v1/user/me",
        headers=user_token_headers,
        json={"profile_image_url": "https://example.com/image.jpg"},
    )
    assert response.status_code == 200

    # 4. Verify all updates
    response = await client.get("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["name"] == "Name 1"
    assert profile["email"] == "newemail@test.com"
    assert profile["profile_image_url"] == "https://example.com/image.jpg"


@pytest.mark.asyncio
async def test_error_recovery_flow(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test error handling and recovery in workflows"""
    # 1. Try to update with invalid email
    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json={"email": "invalid-email"}
    )
    assert response.status_code == 422

    # 2. Verify profile unchanged
    response = await client.get("/api/v1/user/me", headers=user_token_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email

    # 3. Try correct update
    response = await client.patch(
        "/api/v1/user/me", headers=user_token_headers, json={"email": "valid@test.com"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "valid@test.com"
