from typing import Annotated, Any
import base64

from fastapi import APIRouter, Depends, Request, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    DuplicateValueException,
    NotFoundException,
    UnauthorizedException,
)
from ...core.logger import get_logger
from ...core.security import (
    verify_password,
    get_password_hash,
    blacklist_tokens,
    oauth2_scheme,
)
from ...core.utils.file_utils import _detect_image_type
from ...crud.crud_device import crud_device
from ...crud.crud_users import crud_users
from ...schemas.user import UserRead, UserUpdate, PasswordChange
from ...schemas.device import DeviceRead
from ...schemas.base import PaginatedResponse, SuccessResponse

router = APIRouter(tags=["users"])

logger = get_logger(__name__)


@router.get("/user/me/", response_model=UserRead)
async def read_users_me(
    request: Request, current_user: Annotated[dict, Depends(get_current_user)]
) -> dict:
    return current_user


@router.get("/user/devices/", response_model=PaginatedResponse[DeviceRead])
async def get_user_devices(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    List devices owned by the current user (paginated).

    Returns a `PaginatedResponse[DeviceRead]`.
    """
    try:
        logger.debug(f"Listing devices for user {current_user['id']}")

        devices_data = await crud_device.get_multi(
            db=db,
            user_id=current_user["id"],
            offset=(page - 1) * page_size,
            limit=page_size,
            schema_to_select=DeviceRead,
        )

        total = devices_data.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            success=True,
            message="Success",
            data=devices_data["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing user devices: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/user/me", response_model=UserRead)
async def update_user_profile(
    update_data: UserUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> UserRead:
    """
    Update authenticated user's profile information.

    Supports partial updates - only provided fields will be updated.

    Parameters
    ----------
    update_data : UserUpdate
        Fields to update (name, email, profile_image_base64, timezone)
    current_user : dict
        Current authenticated user from JWT token
    db : AsyncSession
        Database session

    Returns
    -------
    UserRead
        Updated user information

    Raises
    ------
    DuplicateValueException
        If new email is already taken by another user
    NotFoundException
        If user not found after update

    Examples
    --------
    Update only name:
        PATCH /user/me
        {"name": "New Name"}

    Update email:
        PATCH /user/me
        {"email": "newemail@example.com"}

    Update profile image (base64):
        PATCH /user/me
        {"profile_image_base64": "data:image/png;base64,iVBORw0KGgo..."}
    """
    try:
        # If email is being changed, check if it's already taken
        if update_data.email and update_data.email != current_user["email"]:
            existing_user = await crud_users.exists(db=db, email=update_data.email)
            if existing_user:
                raise DuplicateValueException("Email is already registered")

        # Update user
        await crud_users.update(db=db, object=update_data, id=current_user["id"])

        # Fetch updated user
        updated_user = await crud_users.get(
            db=db, id=current_user["id"], schema_to_select=UserRead
        )

        if not updated_user:
            raise NotFoundException("User not found after update")

        logger.info(f"User {current_user['id']} updated profile")
        return updated_user

    except (DuplicateValueException, NotFoundException):
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/user/me/password", response_model=SuccessResponse[dict])
async def change_password(
    password_data: PasswordChange,
    current_user: Annotated[dict, Depends(get_current_user)],
    access_token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    request: Request,
) -> SuccessResponse[dict]:
    """
    Change authenticated user's password.

    Requires current password for verification. After successful password change,
    all existing tokens will be invalidated and user must login again.

    Parameters
    ----------
    password_data : PasswordChange
        Current and new password
    current_user : dict
        Current authenticated user from JWT token
    access_token : str
        Current access token (will be blacklisted)
    db : AsyncSession
        Database session
    request : Request
        HTTP request for getting refresh token cookie

    Returns
    -------
    SuccessResponse
        Success message

    Raises
    ------
    UnauthorizedException
        If current password is incorrect
    HTTPException
        If validation fails or internal error

    Examples
    --------
    PUT /user/me/password
    {
        "current_password": "OldPassword123!",
        "new_password": "NewSecurePass456!"
    }
    """
    try:
        # Verify current password
        if not await verify_password(
            password_data.current_password, current_user["hashed_password"]
        ):
            raise UnauthorizedException("Current password is incorrect")

        # Hash new password
        new_hashed_password = get_password_hash(password_data.new_password)

        # Update password
        from ...schemas.user import UserUpdateInternal
        from datetime import datetime, timezone

        update_data = UserUpdateInternal(updated_at=datetime.now(timezone.utc))
        # Manually set hashed_password since it's not in UserUpdate schema
        await crud_users.update(
            db=db,
            object={
                "hashed_password": new_hashed_password,
                "updated_at": update_data.updated_at,
            },
            id=current_user["id"],
        )

        # Blacklist current tokens to force re-login
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            await blacklist_tokens(
                access_token=access_token, refresh_token=refresh_token, db=db
            )

        logger.info(f"User {current_user['id']} changed password")

        return SuccessResponse(
            data={"message": "Password updated successfully. Please login again."}
        )

    except UnauthorizedException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/user/me/profile-image", response_model=SuccessResponse[dict])
async def upload_profile_image(
    file: Annotated[
        UploadFile,
        File(description="Profile image file (jpeg, jpg, png, webp, max 5MB)"),
    ],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[dict]:
    """
    Upload and update user's profile image as base64.

    File is validated, converted to base64, and stored in database.

    Parameters
    ----------
    file : UploadFile
        Image file to upload
    current_user : dict
        Current authenticated user from JWT token
    db : AsyncSession
        Database session

    Returns
    -------
    SuccessResponse
        Success message with base64 image data

    Raises
    ------
    HTTPException 413
        If file exceeds 5MB
    HTTPException 422
        If file type not allowed or not valid image
    HTTPException 500
        If conversion or save fails

    Examples
    --------
    POST /user/me/profile-image
    Content-Type: multipart/form-data

    file: <image binary data>
    """
    try:
        # Validate file size
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / (1024 * 1024):.1f}MB",
            )

        # Validate file extension
        file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
        if file_ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}",
            )

        # Validate image format via magic bytes
        image_type = _detect_image_type(content)
        if not image_type or image_type not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=422, detail="Invalid image file or corrupted data"
            )

        # Convert to base64 with data URI scheme
        base64_data = base64.b64encode(content).decode("utf-8")
        profile_image_base64 = f"data:image/{image_type};base64,{base64_data}"

        # Update user profile
        from ...schemas.user import UserUpdateInternal
        from datetime import datetime, timezone

        await crud_users.update(
            db=db,
            object={
                "profile_image_base64": profile_image_base64,
                "updated_at": datetime.now(timezone.utc),
            },
            id=current_user["id"],
        )

        logger.info(f"User {current_user['id']} uploaded profile image (base64)")

        return SuccessResponse(
            data={
                "profile_image_base64": profile_image_base64,
                "message": "Profile image updated successfully",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile image: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload profile image")


@router.delete("/user/me", response_model=SuccessResponse[dict])
async def delete_user_account(
    current_user: Annotated[dict, Depends(get_current_user)],
    access_token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    request: Request,
) -> SuccessResponse[dict]:
    """
    Soft delete user account.

    Account is marked as deleted but not permanently removed.
    Can be restored within 30 days grace period.
    All tokens are invalidated.

    Parameters
    ----------
    current_user : dict
        Current authenticated user from JWT token
    access_token : str
        Current access token (will be blacklisted)
    db : AsyncSession
        Database session
    request : Request
        HTTP request for getting refresh token

    Returns
    -------
    SuccessResponse
        Success message with deletion details

    Raises
    ------
    HTTPException 400
        If account already deleted
    HTTPException 500
        If deletion fails

    Examples
    --------
    DELETE /user/me
    Authorization: Bearer <token>
    """
    try:
        from datetime import datetime, timezone, timedelta

        # Check if already deleted
        if current_user.get("is_deleted"):
            raise HTTPException(status_code=400, detail="Account is already deleted")

        # Soft delete user
        deleted_at = datetime.now(timezone.utc)
        restore_deadline = deleted_at + timedelta(days=30)

        await crud_users.update(
            db=db,
            object={
                "is_deleted": True,
                "deleted_at": deleted_at,
                "updated_at": deleted_at,
            },
            id=current_user["id"],
        )

        # Blacklist all tokens
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            await blacklist_tokens(
                access_token=access_token, refresh_token=refresh_token, db=db
            )

        logger.info(f"User {current_user['id']} deleted account")

        return SuccessResponse(
            data={
                "message": "Account deleted successfully. You can restore within 30 days.",
                "deleted_at": deleted_at.isoformat(),
                "restore_deadline": restore_deadline.isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user account: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete account")


# Note: Restore endpoint doesn't require authentication (user is deleted)
# So it's added to auth router instead
# See src/app/api/v1/auth.py for POST /auth/restore endpoint
