"""
WebSocket Routes - Migrate từ aiohttp websocket_server.py sang FastAPI
Sử dụng ConnectionHandler từ core/connection.py
Auth + device lookup đã được xử lý ở middleware
"""

import json
from typing import Annotated, Optional

from fastapi import APIRouter, WebSocket, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.connection import ConnectionHandler
from app.ai.utils import AuthToken
from app.api.dependencies import (
    get_websocket_settings,
    get_websocket_thread_pool,
    get_websocket_modules,
    get_agent_service_dependency,
)
from app.core.db.database import async_get_db
from app.core.logger import setup_logging
from starlette.websockets import WebSocketState


TAG = __name__
router = APIRouter()


async def _close_websocket(
    websocket: WebSocket, code: int, reason: str, message: Optional[str] = None
) -> None:
    """
    Đóng websocket một cách an toàn

    Args:
        websocket: WebSocket connection
        code: WebSocket close code
        reason: Lý do đóng kết nối
        message: Thông báo lỗi gửi tới client (nếu có)
    """
    try:
        if message:
            await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass

    try:
        await websocket.close(code=code, reason=reason)
    except Exception:
        pass


async def _authenticate_device(
    websocket: WebSocket,
) -> tuple[Optional[str], Optional[str], Optional[str], bool, Optional[str]]:
    """
    Xác thực device sử dụng AuthToken

    Returns:
        (device_id, client_id, client_ip, is_authenticated, auth_error)
    """
    logger = setup_logging()

    try:
        # Extract auth fields từ headers/query params
        headers_dict = dict(websocket.headers.items())
        query_params = websocket.query_params

        # Device ID: Headers > query params
        device_id = headers_dict.get("device-id") or query_params.get("device-id") or ""

        # Client ID: Headers > query params
        client_id = headers_dict.get("client-id") or query_params.get("client-id") or ""

        # Authorization: Headers > query params
        auth_header = (
            headers_dict.get("authorization") or query_params.get("authorization") or ""
        )

        # Extract token từ auth_header (xử lý "Bearer ", "Bearer+" format)
        token = ""
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif auth_header.startswith("Bearer+"):
                token = auth_header[7:]
            else:
                token = auth_header

        # Nếu không có token, thử query param "token"
        if not token:
            token = query_params.get("token", "")

        # Extract client IP
        client_ip = "unknown"
        if headers_dict.get("x-real-ip"):
            client_ip = headers_dict["x-real-ip"].split(",")[0].strip()
        elif headers_dict.get("x-forwarded-for"):
            client_ip = headers_dict["x-forwarded-for"].split(",")[0].strip()
        elif websocket.client:
            client_ip = websocket.client[0]

        # Validate required fields
        if not device_id or not client_id or not token:
            auth_error = "Missing required auth fields (device-id, client-id, token)"
            logger.bind(tag=TAG).warning(
                f"Missing auth fields: device_id={bool(device_id)}, "
                f"client_id={bool(client_id)}, token={bool(token)}"
            )
            return device_id, client_id, client_ip, False, auth_error

        # Load auth_key từ config để verify token
        try:
            from app.config.config_loader import load_config

            config = load_config()
            server_config = config.get("server", {})
            auth_key = server_config.get("auth_key", "")

            if not auth_key:
                logger.bind(tag=TAG).warning("Missing auth_key in server config")
                return (
                    device_id,
                    client_id,
                    client_ip,
                    False,
                    "Server auth key not configured",
                )

            # Verify token sử dụng AuthToken
            auth_token = AuthToken(secret_key=auth_key)
            is_valid, extracted_device_id = auth_token.verify_token(token)

            if not is_valid or not extracted_device_id:
                logger.bind(tag=TAG).warning(
                    f"Token verification failed for device {device_id}"
                )
                return (
                    device_id,
                    client_id,
                    client_ip,
                    False,
                    "Token verification failed",
                )

            # Verify extracted device_id matches header device_id
            if extracted_device_id != device_id:
                logger.bind(tag=TAG).warning(
                    f"Device ID mismatch: header={device_id}, token={extracted_device_id}"
                )
                return device_id, client_id, client_ip, False, "Device ID mismatch"

            logger.bind(tag=TAG).debug(
                f"[WebSocket] Auth successful: device={device_id}, ip={client_ip}"
            )
            return device_id, client_id, client_ip, True, None

        except Exception as e:
            logger.bind(tag=TAG).error(f"Auth verification error: {e}")
            return device_id, client_id, client_ip, False, f"Auth error: {str(e)}"

    except Exception as e:
        logger.bind(tag=TAG).error(f"[WebSocket] Auth exception: {e}")
        return "unknown", "unknown", "unknown", False, str(e)


async def _load_app_state(websocket: WebSocket, device_id: str):
    """
    Tải settings, thread_pool, modules và agent từ app state

    Returns:
        (settings, thread_pool, modules, agent)
    """
    logger = setup_logging()

    try:
        settings = get_websocket_settings(websocket)
        thread_pool = get_websocket_thread_pool(websocket)
        modules = get_websocket_modules(websocket)
        agent_service = get_agent_service_dependency()

        db = async_get_db()
        async for session in db:
            agent = await agent_service.get_agent_from_ws(
                db=session, mac_address=device_id
            )
            break

        if hasattr(settings, "to_dict"):
            config_dict = settings.to_dict()
        elif hasattr(settings, "model_dump"):
            config_dict = settings.model_dump()
        else:
            config_dict = settings

        logger.bind(tag=TAG).info("[WebSocket] App state loaded successfully")
        return settings, thread_pool, modules, agent, agent_service, config_dict

    except RuntimeError as e:
        logger.bind(tag=TAG).error(f"[WebSocket] State initialization error: {e}")
        raise RuntimeError(f"Server not ready: {e}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"[WebSocket] Unexpected state error: {e}")
        raise


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint - Optimize flow với full error handling

    Flow:
    1. Authenticate device (reject nếu auth fail)
    2. Load app state (settings, modules, agent)
    3. Accept websocket connection
    4. Handle connection với ConnectionHandler
    5. Clean up nếu có error
    """
    logger = setup_logging()
    handler = None
    logger.debug("websocket_endpoint")

    try:
        logger.bind(tag=TAG).debug("[WebSocket] Client attempting to connect")
        logger.bind(tag=TAG).debug(f"[WebSocket] Headers: {websocket.headers}")
        logger.bind(tag=TAG).debug(
            f"[WebSocket] Query params: {websocket.query_params}"
        )

        # Step 1: Authenticate device
        device_id, client_id, client_ip, is_authenticated, auth_error = (
            await _authenticate_device(websocket)
        )

        if auth_error:
            await websocket.accept()
            logger.bind(tag=TAG).warning(
                f"[WebSocket] Authentication rejected: {auth_error}"
            )
            await _close_websocket(
                websocket,
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Auth failed",
                message=f"Xác thực thất bại: {auth_error}",
            )
            return

        # Step 2: Load app state
        try:
            settings, thread_pool, modules, agent, agent_service, config_dict = (
                await _load_app_state(websocket, device_id)
            )
        except RuntimeError as e:
            await websocket.accept()
            await _close_websocket(
                websocket,
                code=status.WS_1011_SERVER_ERROR,
                reason="Server not ready",
                message="Server chưa sẵn sàng",
            )
            return
        logger.bind(tag=TAG).debug(f"[WebSocket] Agent = {agent}")

        # Validate agent
        if agent is None:
            logger.bind(tag=TAG).warning(
                f"[WebSocket] No agent found for device {device_id}, rejecting connection"
            )
            await websocket.accept()
            await _close_websocket(
                websocket,
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid device",
                message="Thiết bị không hợp lệ hoặc chưa xác thực",
            )
            return

        # Step 3: Accept connection
        await websocket.accept()
        logger.bind(tag=TAG).debug("[WebSocket] Client connection accepted")
        logger.bind(tag=TAG).info(
            f"[WebSocket] Client connected from {client_ip}, "
            f"device={device_id}, authenticated={is_authenticated}"
        )

        # Step 4: Create handler and handle connection
        handler = ConnectionHandler(
            config=config_dict,
            _vad=modules.get("vad"),
            _asr=modules.get("asr"),
            _llm=modules.get("llm"),
            _memory=modules.get("memory"),
            _intent=modules.get("intent"),
            thread_pool=thread_pool,
            server=websocket.app.state,
            agent=agent,
            agent_service=agent_service,
        )

        # Register handler if tracking active connections
        if hasattr(websocket.app.state, "active_connections"):
            websocket.app.state.active_connections.add(handler)

        try:
            await handler.handle_connection(websocket)
        except Exception as e:
            logger.bind(tag=TAG).error(f"[WebSocket] Error handling connection: {e}")
            import traceback

            traceback.print_exc()

    except Exception as e:
        # Catch any unexpected errors and close websocket
        logger.bind(tag=TAG).error(f"[WebSocket] Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        await _close_websocket(
            websocket,
            code=status.WS_1011_SERVER_ERROR,
            reason="Internal error",
            message="Lỗi máy chủ nội bộ",
        )
    finally:
        # Cleanup
        if handler is not None and hasattr(websocket.app.state, "active_connections"):
            websocket.app.state.active_connections.discard(handler)

        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as e:
            logger.bind(tag=TAG).debug(
                f"[WebSocket] Error closing websocket (ignored): {e}"
            )
