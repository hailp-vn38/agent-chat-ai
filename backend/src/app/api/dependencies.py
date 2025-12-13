from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.config import Settings
from app.core.auth import AuthManager
from app.services import ThreadPoolService
from ..core.db.database import async_get_db
from ..core.exceptions.http_exceptions import (
    ForbiddenException,
    UnauthorizedException,
)
from ..core.logger import get_logger
from ..core.security import TokenType, oauth2_scheme, verify_token
from ..core.utils import BaseCacheManager, get_cache_manager
from ..crud.crud_users import crud_users
from ..crud.crud_device import crud_device
from ..services.agent_service import agent_service


logger = get_logger(__name__)


async def get_settings(request: Request) -> Settings:
    """Lấy cấu hình ứng dụng từ app state."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        raise HTTPException(
            status_code=503,
            detail="Settings not initialized",
        )
    return config


async def get_thread_pool(request: Request) -> ThreadPoolService:
    """Lấy thread pool dùng cho tác vụ blocking."""
    thread_pool = getattr(request.app.state, "thread_pool", None)
    if thread_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Thread pool not initialized",
        )
    return thread_pool


async def get_redis_client(request: Request) -> Redis:
    """Lấy Redis client từ cache pool.

    Raises:
        HTTPException: Nếu Redis client chưa được khởi tạo
    """
    from app.core.utils.cache import client as redis_client

    if redis_client is None:
        raise HTTPException(
            status_code=503,
            detail="Redis cache not initialized",
        )
    return redis_client


async def get_modules(request: Request) -> dict[str, Any]:
    """Lấy các mô-đun đã khởi tạo (VAD, ASR, LLM, ...)."""
    modules = getattr(request.app.state, "modules", None)
    if modules is None:
        raise HTTPException(
            status_code=503,
            detail="Modules not initialized",
        )
    return modules


async def get_device_id(request: Request) -> str:
    """Đọc device-id từ header yêu cầu."""
    device_id = request.headers.get("device-id")
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing device-id header")
    return device_id


def get_websocket_settings(websocket: WebSocket) -> Settings:
    """Lấy cấu hình từ state trong WebSocket."""
    if not hasattr(websocket.app.state, "config"):
        raise RuntimeError("Settings not initialized")
    return websocket.app.state.config


def get_websocket_thread_pool(websocket: WebSocket) -> ThreadPoolService:
    """Lấy thread pool từ WebSocket state."""
    if not hasattr(websocket.app.state, "thread_pool"):
        raise RuntimeError("Thread pool not initialized")
    return websocket.app.state.thread_pool


def get_websocket_modules(websocket: WebSocket) -> dict[str, Any]:
    """Lấy các mô-đun đã khởi tạo từ WebSocket state."""
    if not hasattr(websocket.app.state, "modules"):
        raise RuntimeError("Modules not initialized")
    return websocket.app.state.modules


def get_websocket_auth_manager(websocket: WebSocket) -> AuthManager | None:
    """Lấy AuthManager đang được bật (nếu có)."""
    return getattr(websocket.app.state, "auth_manager", None)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> dict[str, Any] | None:
    token_data = await verify_token(token, TokenType.ACCESS, db)
    if token_data is None:
        raise UnauthorizedException("User not authenticated.")

    # Token now contains email in username_or_email field
    user = await crud_users.get(
        db=db, email=token_data.username_or_email, is_deleted=False
    )

    if user:
        if hasattr(user, "model_dump"):
            return user.model_dump()
        else:
            return user

    raise UnauthorizedException("User not authenticated.")


async def get_optional_user(
    request: Request, db: AsyncSession = Depends(async_get_db)
) -> dict | None:
    token = request.headers.get("Authorization")
    if not token:
        return None

    try:
        token_type, _, token_value = token.partition(" ")
        if token_type.lower() != "bearer" or not token_value:
            return None

        token_data = await verify_token(token_value, TokenType.ACCESS, db)
        if token_data is None:
            return None

        return await get_current_user(token_value, db=db)

    except HTTPException as http_exc:
        if http_exc.status_code != 401:
            logger.error(
                f"Unexpected HTTPException in get_optional_user: {http_exc.detail}"
            )
        return None

    except Exception as exc:
        logger.error(f"Unexpected error in get_optional_user: {exc}")
        return None


async def get_current_superuser(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    if not current_user["is_superuser"]:
        raise ForbiddenException("You do not have enough privileges.")

    return current_user


async def get_cache_manager_dependency() -> BaseCacheManager:
    """
    Get cache manager instance for async FastAPI dependency injection.

    This is the async wrapper for get_cache_manager to be used with Depends().

    Returns:
        BaseCacheManager: RedisCacheManager instance

    Raises:
        MissingClientError: If Redis client is not initialized
    """
    return get_cache_manager()


def get_agent_service_dependency():
    """Lấy AgentService instance cho dependency injection."""
    return agent_service
