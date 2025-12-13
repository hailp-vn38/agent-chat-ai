"""Utility functions for file operations and validation."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile, HTTPException

from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


def _detect_image_type(content: bytes) -> Optional[str]:
    """
    Detect image type from magic bytes (replacement for imghdr).

    Returns:
        Image type string ('jpeg', 'png', 'webp') or None
    """
    if len(content) < 4:
        return None

    # JPEG: FF D8 FF
    if content[:3] == b"\xff\xd8\xff":
        return "jpeg"

    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if content[:8] == b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a":
        return "png"

    # WebP: RIFF ... WEBP
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"

    return None


async def validate_image_file(file: UploadFile) -> bool:
    """
    Validate uploaded image file.

    Checks:
    - File size within limit
    - File extension allowed
    - File is actual image (magic bytes check)

    Parameters
    ----------
    file : UploadFile
        Uploaded file to validate

    Returns
    -------
    bool
        True if valid

    Raises
    ------
    HTTPException
        If validation fails
    """
    # Check file size
    content = await file.read()
    file_size = len(content)
    await file.seek(0)  # Reset file pointer

    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB limit",
        )

    # Check extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}",
        )

    # Validate actual image content (magic bytes)
    image_type = _detect_image_type(content)
    if not image_type or image_type not in ["jpeg", "png", "webp"]:
        raise HTTPException(status_code=422, detail="File is not a valid image")

    return True


async def save_profile_image(file: UploadFile, user_id: str) -> str:
    """
    Save uploaded profile image to disk.

    Creates user-specific directory and saves file with timestamp.

    Parameters
    ----------
    file : UploadFile
        Image file to save
    user_id : str
        User ID for directory organization

    Returns
    -------
    str
        Relative path to saved file

    Raises
    ------
    HTTPException
        If save operation fails
    """
    try:
        # Validate file first
        await validate_image_file(file)

        # Create user directory
        user_dir = Path(settings.UPLOAD_DIR) / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = int(datetime.now().timestamp())
        file_ext = file.filename.split(".")[-1].lower() if file.filename else "jpg"
        filename = f"original_{timestamp}.{file_ext}"

        # Save file
        file_path = user_dir / filename
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        # Return relative path for URL
        relative_path = f"{settings.UPLOAD_DIR}/{user_id}/{filename}"
        logger.info(f"Saved profile image for user {user_id}: {relative_path}")

        return relative_path

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving profile image: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save profile image")


async def delete_old_profile_image(
    user_id: str, exclude_filename: Optional[str] = None
) -> None:
    """
    Delete old profile images for a user.

    Optionally keeps a specific file (e.g., the new one).

    Parameters
    ----------
    user_id : str
        User ID
    exclude_filename : Optional[str]
        Filename to keep (not delete)
    """
    try:
        user_dir = Path(settings.UPLOAD_DIR) / user_id

        if not user_dir.exists():
            return

        for file_path in user_dir.glob("original_*"):
            if exclude_filename and file_path.name == exclude_filename:
                continue

            try:
                file_path.unlink()
                logger.info(f"Deleted old profile image: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

    except Exception as e:
        logger.error(f"Error deleting old profile images: {e}")
        # Don't raise - deletion failure shouldn't block upload
