from datetime import timedelta
from typing import Annotated, Optional, cast

from fastapi import APIRouter, Cookie, Depends, Request, Response, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    DuplicateValueException,
    NotFoundException,
    UnauthorizedException,
)
from ...core.logger import get_logger
from ...core.schemas import Token
from ...core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TokenType,
    authenticate_user,
    blacklist_tokens,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    oauth2_scheme,
    verify_token,
)
from ...crud.crud_users import crud_users
from ...schemas.user import UserCreate, UserCreateInternal, UserRead
from ...schemas.base import SuccessResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    request: Request,
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> UserRead:
    """Register a new user.

    Parameters
    ----------
    request : Request
        The HTTP request object
    user : UserCreate
        The user registration data (name, email, password)
    db : AsyncSession
        Database session for performing database operations

    Returns
    -------
    UserRead
        The created user with HTTP 201 status

    Raises
    ------
    DuplicateValueException
        If email already exists
    NotFoundException
        If created user cannot be retrieved
    """
    email_row = await crud_users.exists(db=db, email=user.email)
    if email_row:
        raise DuplicateValueException("Email is already registered")

    user_internal_dict = user.model_dump()
    user_internal_dict["hashed_password"] = get_password_hash(
        password=user_internal_dict["password"]
    )
    del user_internal_dict["password"]

    user_internal = UserCreateInternal(**user_internal_dict)
    created_user = await crud_users.create(
        db=db, object=user_internal, schema_to_select=UserRead, return_as_model=True
    )

    user_read = await crud_users.get(
        db=db, id=created_user.id, schema_to_select=UserRead, return_as_model=True
    )
    if user_read is None:
        raise NotFoundException("Created user not found")

    return cast(UserRead, user_read)


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, str]:
    """Authenticate user and return JWT tokens.

    Parameters
    ----------
    response : Response
        The HTTP response object for setting cookies
    form_data : OAuth2PasswordRequestForm
        Email (in username field) and password credentials
    db : AsyncSession
        Database session for performing database operations

    Returns
    -------
    dict
        Dictionary with access_token and token_type="bearer"

    Raises
    ------
    UnauthorizedException
        If credentials are invalid
    """
    user = await authenticate_user(
        username_or_email=form_data.username, password=form_data.password, db=db
    )
    if not user:
        raise UnauthorizedException("Wrong email or password.")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )

    refresh_token = await create_refresh_token(data={"sub": user["email"]})
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=max_age,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh(
    request: Request,
    db: AsyncSession = Depends(async_get_db),
) -> dict[str, str]:
    """Refresh access token using refresh token from cookie.

    Parameters
    ----------
    request : Request
        The HTTP request object containing refresh_token cookie
    db : AsyncSession
        Database session for performing database operations

    Returns
    -------
    dict
        Dictionary with new access_token and token_type="bearer"

    Raises
    ------
    UnauthorizedException
        If refresh token is missing, invalid, or expired
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise UnauthorizedException("Refresh token missing.")

    user_data = await verify_token(refresh_token, TokenType.REFRESH, db)
    if not user_data:
        raise UnauthorizedException("Invalid refresh token.")

    new_access_token = await create_access_token(
        data={"sub": user_data.username_or_email}
    )
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    response: Response,
    access_token: str = Depends(oauth2_scheme),
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(async_get_db),
) -> dict[str, str]:
    """Logout user by blacklisting tokens and clearing cookies.

    Parameters
    ----------
    response : Response
        The HTTP response object for clearing cookies
    access_token : str
        The current access token from Bearer scheme
    refresh_token : Optional[str]
        The refresh token from cookie
    db : AsyncSession
        Database session for performing database operations

    Returns
    -------
    dict
        Dictionary with success message

    Raises
    ------
    UnauthorizedException
        If refresh token is not found or tokens are invalid
    """
    if not refresh_token:
        raise UnauthorizedException("Refresh token not found")

    await blacklist_tokens(
        access_token=access_token, refresh_token=refresh_token, db=db
    )
    response.delete_cookie(key="refresh_token")

    return {"message": "Logged out successfully"}


@router.post("/restore", response_model=SuccessResponse[dict])
async def restore_deleted_account(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> SuccessResponse[dict]:
    """
    Restore soft-deleted user account.

    User can restore their account within 30 days of deletion
    by providing email and password. After successful restore,
    new tokens are issued.

    Parameters
    ----------
    response : Response
        HTTP response for setting cookies
    form_data : OAuth2PasswordRequestForm
        Email (in username field) and password
    db : AsyncSession
        Database session

    Returns
    -------
    SuccessResponse
        Success message with new access token

    Raises
    ------
    UnauthorizedException
        If credentials invalid or account not found
    HTTPException 400
        If account is not deleted
    HTTPException 410
        If grace period expired (>30 days)

    Examples
    --------
    POST /auth/restore
    username=user@example.com&password=Password123!
    """
    try:
        from datetime import datetime, timezone, timedelta

        # Get deleted user (include deleted in query)
        user = await crud_users.get(
            db=db, email=form_data.username, is_deleted=True  # Only get deleted users
        )

        if not user:
            raise UnauthorizedException("Invalid email or password")

        # Verify password
        from ...core.security import verify_password

        if not await verify_password(form_data.password, user["hashed_password"]):
            raise UnauthorizedException("Invalid email or password")

        # Check if not actually deleted
        if not user.get("is_deleted"):
            raise HTTPException(status_code=400, detail="Account is not deleted")

        # Check grace period (30 days)
        deleted_at = user.get("deleted_at")
        if deleted_at:
            grace_period = timedelta(days=30)
            if datetime.now(timezone.utc) - deleted_at > grace_period:
                raise HTTPException(
                    status_code=410,
                    detail="Restore period expired. Account permanently deleted.",
                )

        # Restore account
        await crud_users.update(
            db=db,
            object={
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc),
            },
            id=user["id"],
        )

        # Create new tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = await create_access_token(
            data={"sub": user["email"]}, expires_delta=access_token_expires
        )

        refresh_token = await create_refresh_token(data={"sub": user["email"]})
        max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=max_age,
        )

        logger.info(f"User {user['id']} restored account")

        return SuccessResponse(
            data={
                "message": "Account restored successfully",
                "access_token": access_token,
                "token_type": "bearer",
            }
        )

    except (UnauthorizedException, HTTPException):
        raise
    except Exception as e:
        logger.error(f"Error restoring account: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to restore account")
