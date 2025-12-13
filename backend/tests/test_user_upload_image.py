"""
Tests for profile image upload endpoint (POST /api/v1/user/me/profile-image)
"""

import io
import os
from pathlib import Path

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.user import User


def create_test_image(format: str = "JPEG", size: tuple = (100, 100)) -> bytes:
    """Create a test image in memory"""
    img = Image.new("RGB", size, color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format=format)
    img_bytes.seek(0)
    return img_bytes.read()


@pytest.mark.asyncio
async def test_upload_profile_image_success(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test successful profile image upload"""
    image_data = create_test_image()

    files = {"file": ("profile.jpg", image_data, "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "profile_image_url" in data["data"]
    assert data["data"]["profile_image_url"] is not None
    assert "static/uploads/profiles" in data["data"]["profile_image_url"]

    # Verify in database
    await async_session.refresh(test_user)
    assert test_user.profile_image_url == data["data"]["profile_image_url"]


@pytest.mark.asyncio
async def test_upload_profile_image_png(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test uploading PNG image"""
    image_data = create_test_image(format="PNG")

    files = {"file": ("profile.png", image_data, "image/png")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert ".png" in data["data"]["profile_image_url"]


@pytest.mark.asyncio
async def test_upload_profile_image_webp(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test uploading WebP image"""
    image_data = create_test_image(format="WEBP")

    files = {"file": ("profile.webp", image_data, "image/webp")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    assert response.status_code == 200
    data = response.json()
    assert ".webp" in data["data"]["profile_image_url"]


@pytest.mark.asyncio
async def test_upload_profile_image_too_large(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test uploading image larger than 5MB returns 413"""
    # Create a large image (> 5MB)
    large_image_data = create_test_image(size=(3000, 3000))
    # Make it even larger by repeating
    large_image_data = large_image_data * 10

    files = {"file": ("large.jpg", large_image_data, "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    # Should return 413 or 422 depending on validation
    assert response.status_code in [413, 422]


@pytest.mark.asyncio
async def test_upload_invalid_file_type(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test uploading non-image file returns 422"""
    # Create a text file
    text_data = b"This is not an image"

    files = {"file": ("document.txt", text_data, "text/plain")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_fake_image_extension(
    client: AsyncClient, user_token_headers: dict[str, str]
):
    """Test uploading text file with .jpg extension returns 422"""
    # Create text data with image extension
    text_data = b"This is not an image but has .jpg extension"

    files = {"file": ("fake.jpg", text_data, "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    # Should be rejected by magic bytes validation
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_no_file(client: AsyncClient, user_token_headers: dict[str, str]):
    """Test upload without file returns 422"""
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_replaces_existing_image(
    client: AsyncClient,
    test_user: User,
    user_token_headers: dict[str, str],
    async_session: AsyncSession,
):
    """Test uploading new image replaces existing one"""
    # Upload first image
    image_data_1 = create_test_image()
    files = {"file": ("profile1.jpg", image_data_1, "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )
    assert response.status_code == 200
    first_url = response.json()["data"]["profile_image_url"]

    # Upload second image
    image_data_2 = create_test_image()
    files = {"file": ("profile2.jpg", image_data_2, "image/jpeg")}
    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )
    assert response.status_code == 200
    second_url = response.json()["data"]["profile_image_url"]

    # URLs should be different
    assert first_url != second_url

    # Verify in database
    await async_session.refresh(test_user)
    assert test_user.profile_image_url == second_url


@pytest.mark.asyncio
async def test_upload_unauthenticated(client: AsyncClient):
    """Test upload without authentication returns 401"""
    image_data = create_test_image()
    files = {"file": ("profile.jpg", image_data, "image/jpeg")}

    response = await client.post("/api/v1/user/me/profile-image", files=files)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_creates_directory_structure(
    client: AsyncClient, test_user: User, user_token_headers: dict[str, str]
):
    """Test that upload creates necessary directories"""
    image_data = create_test_image()
    files = {"file": ("profile.jpg", image_data, "image/jpeg")}

    response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )

    assert response.status_code == 200
    data = response.json()
    url = data["data"]["profile_image_url"]

    # Extract file path from URL
    # URL format: /static/uploads/profiles/{user_id}/original_{timestamp}.{ext}
    # Check directory exists
    if "static/uploads/profiles" in url:
        path_part = url.split("/static/uploads/profiles/")[1]
        user_id_part = path_part.split("/")[0]
        upload_dir = Path(f"static/uploads/profiles/{user_id_part}")

        # Directory should exist after upload
        assert upload_dir.exists()


@pytest.mark.asyncio
async def test_upload_different_users_different_dirs(
    client: AsyncClient,
    test_user: User,
    test_superuser: User,
    user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
):
    """Test that different users have separate upload directories"""
    image_data = create_test_image()

    # User uploads
    files = {"file": ("user_profile.jpg", image_data, "image/jpeg")}
    user_response = await client.post(
        "/api/v1/user/me/profile-image", headers=user_token_headers, files=files
    )
    assert user_response.status_code == 200
    user_url = user_response.json()["data"]["profile_image_url"]

    # Superuser uploads
    files = {"file": ("superuser_profile.jpg", image_data, "image/jpeg")}
    superuser_response = await client.post(
        "/api/v1/user/me/profile-image", headers=superuser_token_headers, files=files
    )
    assert superuser_response.status_code == 200
    superuser_url = superuser_response.json()["data"]["profile_image_url"]

    # URLs should have different user IDs
    assert user_url != superuser_url
    assert str(test_user.id) in user_url
    assert str(test_superuser.id) in superuser_url
