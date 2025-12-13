"""OTA (Over-The-Air) Update Routes"""

import json
import time
import base64
import hashlib
import hmac
import random
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.schemas import OTADeviceData
from app.config import Settings
from app.services import ThreadPoolService
from app.api.dependencies import (
    get_settings,
    get_thread_pool,
    get_cache_manager_dependency,
)
from app.core.auth import AuthManager
from app.ai.utils import get_local_ip, AuthToken
from app.crud.crud_device import crud_device
from app.core.db.database import async_get_db
from app.core.utils import CacheKey, BaseCacheManager
from ...core.logger import get_logger
from app.core.utils.timezone import resolve_timezone

router = APIRouter(prefix="/ota", tags=["ota"])

logger = get_logger(__name__)

# Cache expiration for device validation (5 minutes)
DEVICE_VALIDATION_CACHE_TTL = 300

# Constants
ACTIVATION_CODE_LENGTH = 6


async def _validate_device_exists(
    db: AsyncSession,
    mac_address: str,
    redis_client: Redis | None = None,
) -> bool:
    """
    Validate device exists in database with Redis caching.

    Cache pattern: device_validated:{mac_address}
    Cache TTL: 5 minutes (300 seconds)

    Args:
        db: AsyncSession for database operations
        mac_address: MAC address of device (AA:BB:CC:DD:EE:FF format)
        redis_client: Redis client for caching (optional)

    Returns:
        bool: True if device exists and is not deleted, False otherwise

    Raises:
        HTTPException: If device not found (401 Unauthorized)
    """
    cache_key = f"device_validated:{mac_address}"

    # Try to get from Redis cache
    if redis_client:
        try:
            cached_result = await redis_client.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Device validation cache hit for {mac_address}")
                return cached_result.decode() == "true"
        except Exception as e:
            logger.warning(f"Cache read error for {mac_address}: {e}")
            # Continue to database query if cache fails

    # Query database if not in cache
    try:
        device = await crud_device.get_device_by_mac_address(
            db=db,
            mac_address=mac_address,
            include_deleted=False,
        )

        device_exists = device is not None

        # Cache the result
        if redis_client:
            try:
                cache_value = "true" if device_exists else "false"
                await redis_client.set(
                    cache_key,
                    cache_value,
                    ex=DEVICE_VALIDATION_CACHE_TTL,
                )
                logger.debug(
                    f"Cached device validation for {mac_address}: {cache_value}"
                )
            except Exception as e:
                logger.warning(f"Cache write error for {mac_address}: {e}")

        if not device_exists:
            logger.warning(f"Device not found for MAC address: {mac_address}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Device {mac_address} not authorized",
            )

        return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Device validation error for {mac_address}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device validation failed: {str(e)}",
        )


@router.options("", include_in_schema=False)
async def ota_options():
    """Handle CORS preflight requests"""
    return {}


def _add_cors_headers(response):
    """Thêm header CORS"""
    response.headers["Access-Control-Allow-Headers"] = (
        "client-id, content-type, device-id"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Origin"] = "*"


def generate_password_signature(content: str, secret_key: str) -> str:
    """Tạo chữ ký mật khẩu MQTT

    Args:
        content: Nội dung dùng để ký (clientId + '|' + username)
        secret_key: Khóa bí mật

    Returns:
        str: Chữ ký HMAC-SHA256 được mã hóa Base64
    """
    try:
        hmac_obj = hmac.new(
            secret_key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256
        )
        signature = hmac_obj.digest()
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        print(f"Tạo chữ ký mật khẩu MQTT thất bại: {e}")
        return ""


def get_websocket_url(settings: Settings, local_ip: str) -> str:
    """Lấy địa chỉ websocket

    Args:
        settings: Settings object với server config
        local_ip: Địa chỉ IP cục bộ

    Returns:
        str: Địa chỉ websocket
    """
    config = settings.to_dict()
    server_config = config.get("server", {})
    websocket_config = server_config.get("websocket", "")

    if websocket_config and "你的" not in websocket_config:
        return websocket_config
    else:
        port = settings.server.port
        return f"ws://{local_ip}:{port}/api/v1/"


@router.get("", response_model=dict, include_in_schema=True)
async def ota_get(
    settings: Settings = Depends(get_settings),
):
    """
    OTA GET - Returns WebSocket URL and status (handle_get)
    """
    try:
        local_ip = get_local_ip()
        websocket_url = get_websocket_url(settings, local_ip)

        message = f"OTA hoạt động bình thường, địa chỉ websocket gửi cho thiết bị là: {websocket_url}"
        return {"message": message, "websocket_url": websocket_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTA giao diện gặp lỗi: {str(e)}",
        )


@router.post("", response_model=dict)
async def ota_post(
    device_data: OTADeviceData,
    device_id: str = Header(..., alias="device-id"),
    client_id: str = Header(..., alias="client-id"),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(async_get_db),
    cache: Annotated[BaseCacheManager, Depends(get_cache_manager_dependency)] = None,
):
    """
    OTA POST - Sends firmware config (MQTT or WebSocket) (handle_post)

    NEW LOGIC:
    - If device exists in DB → Send normal response (no activation)
    - If device NOT in DB → Generate activation code, store device data in Redis (24h TTL)

    Validates device exists in database when auth is enabled.
    """

    # device_id: Địa chỉ MAC thiết bị
    try:
        data = device_data.model_dump()

        # Load config từ YAML file
        from app.config.config_loader import load_config

        config = load_config()
        server_config = config.get("server", {})
        local_ip = get_local_ip()

        tz_name = server_config.get("tz", "UTC")
        tz_info = resolve_timezone(tz_name)
        offset = datetime.now(tz_info).utcoffset()
        offset_minutes = int(offset.total_seconds() // 60) if offset else 0

        return_json = {
            "server_time": {
                "timestamp": int(round(time.time() * 1000)),
                "timezone_offset": offset_minutes,
            },
            "firmware": {
                "version": data.get("application", {}).get("version", "1.0.0"),
                "url": "",
            },
        }

        # ============ NEW LOGIC: Check if device exists ============
        device_exists = await crud_device.get_device_by_mac_address(
            db=db, mac_address=device_id
        )

        if not device_exists:
            # Device not in DB → Store activation data in Redis + generate activation code
            logger.info(f"Device {device_id} not in DB. Generating activation code.")

            # Generate activation code
            activation_code = "".join(
                random.choices("0123456789", k=ACTIVATION_CODE_LENGTH)
            )
            logger.debug(
                f"Generated activation code: {activation_code} for MAC {device_id}"
            )

            # Store activation code + OTA device data in Redis (24h TTL) - single operation
            try:
                activation_payload = {
                    "code": activation_code,
                    "device_data": data,
                }
                # Store under mac_address key
                await cache.set(
                    CacheKey.DEVICE_ACTIVATION, activation_payload, device_id
                )
                # Also store code->mac mapping for reverse lookup
                await cache.set(CacheKey.ACTIVATION_CODE, device_id, activation_code)
            except Exception as e:
                logger.error(f"Failed to store device activation data: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to store device activation data",
                )

            # Add activation info to response
            activation_challenge = base64.b64encode(
                hashlib.sha256(activation_code.encode()).digest()
            ).decode("utf-8")[:32]

            return_json["activation"] = {
                "message": f"Mã kích hoạt: {activation_code}",
                "code": activation_code,
                "challenge": activation_challenge,
                "timeout_ms": 30000,
            }

            logger.info(
                f"OTA activation data prepared for device {device_id} with code {activation_code}"
            )

        # ============ Device exists → Normal response ============
        logger.info(f"Device {device_id} found in DB. Sending normal config.")

        mqtt_gateway_endpoint = server_config.get("mqtt_gateway")

        if mqtt_gateway_endpoint:
            device_model = "default"
            try:
                if "device" in data and isinstance(data["device"], dict):
                    device_model = data["device"].get("model", "default")
                elif "model" in data:
                    device_model = data["model"]
                group_id = f"GID_{device_model}".replace(":", "_").replace(" ", "_")
            except Exception as e:
                logger.error(f"Failed to get device model: {e}")
                group_id = "GID_default"

            mac_address_safe = device_id.replace(":", "_")
            mqtt_client_id = f"{group_id}@@@{mac_address_safe}@@@{mac_address_safe}"

            user_data = {"ip": "unknown"}
            try:
                user_data_json = json.dumps(user_data)
                username = base64.b64encode(user_data_json.encode("utf-8")).decode(
                    "utf-8"
                )
            except Exception as e:
                logger.error(f"Failed to create username: {e}")
                username = ""

            password = ""
            signature_key = server_config.get("mqtt_signature_key", "")
            if signature_key:
                password = generate_password_signature(
                    mqtt_client_id + "|" + username, signature_key
                )
                if not password:
                    password = ""
            else:
                logger.warning("Missing MQTT signature key, password is empty")

            return_json["mqtt"] = {
                "endpoint": mqtt_gateway_endpoint,
                "client_id": mqtt_client_id,
                "username": username,
                "password": password,
                "publish_topic": f"server/{device_id}/audio",
            }
            logger.debug(f"Gửi cấu hình MQTT Gateway cho thiết bị {device_id}")

            # Add MQTT common config for receiving messages from server
            # Lấy từ config (mqtt section)
            mqtt_common_config = config.get("mqtt", {})
            if mqtt_common_config:
                return_json["mqtt_common"] = {
                    "endpoint": mqtt_common_config.get("url", ""),
                    "username": mqtt_common_config.get("username", ""),
                    "password": mqtt_common_config.get("password", ""),
                    "subscribe_topic": f"device/{device_id}/#",
                }
                logger.debug(f"Gửi cấu hình MQTT Common cho thiết bị {device_id}")
        else:
            token = ""
            auth_config = server_config.get("auth", {})
            auth_enable = auth_config.get("enabled", False)
            if auth_enable:
                # Device exists, check if it's in allowed devices
                allowed_devices = set(auth_config.get("allowed_devices", []))
                # Deny access if allowed_devices is specified and device not in it
                if allowed_devices and device_id not in allowed_devices:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Device {device_id} not authorized",
                    )
                # Generate token using AuthToken with auth_key from server_config
                auth_key = server_config.get("auth_key", "")
                if auth_key:
                    auth_token = AuthToken(secret_key=auth_key)
                    token = auth_token.generate_token(device_id=device_id)
                    logger.debug(
                        f"Generated AuthToken device token for device {device_id}"
                    )
                else:
                    logger.warning(
                        f"Missing auth_key in server_config for device {device_id}"
                    )
                    token = ""

            return_json["websocket"] = {
                "url": get_websocket_url(settings, local_ip),
                "token": token,
            }
            logger.debug(
                f"Không cấu hình MQTT Gateway, gửi cấu hình WebSocket cho thiết bị {device_id}"
            )
            logger.debug(f"Response: {return_json}")

        # Always add MQTT common config for device to receive messages (ngoài điều kiện mqtt_gateway)
        mqtt_common_config = config.get("mqtt", {})
        if mqtt_common_config:
            return_json["mqtt_common"] = {
                "endpoint": mqtt_common_config.get("url", ""),
                "username": mqtt_common_config.get("username", ""),
                "password": mqtt_common_config.get("password", ""),
                "subscribe_topic": f"device/{device_id}/#",
            }
            logger.debug(f"Gửi cấu hình MQTT Common cho thiết bị {device_id}")

        return return_json

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Request error: {str(e)}",
        )


@router.post("/download")
async def ota_download(
    device_id: str = Header(..., alias="device-id"),
    version: str = Header(...),
    thread_pool: ThreadPoolService = Depends(get_thread_pool),
):
    """Download firmware file"""

    def _prepare_download_sync():
        return {"file_path": None, "size": 0, "checksum": None}

    try:
        file_info = await thread_pool.run_blocking(_prepare_download_sync)

        if not file_info["file_path"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Firmware version {version} not found",
            )

        return {"message": "Download not yet implemented"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/activate", response_model=dict, include_in_schema=True)
async def ota_activate(
    device_id: str = Header(..., alias="device-id"),
    db: AsyncSession = Depends(async_get_db),
    cache: Annotated[BaseCacheManager, Depends(get_cache_manager_dependency)] = None,
):
    """
    OTA Activate - Confirm device activation

    Logic:
    - If device exists in DB → Status 200 (success)
    - If device NOT in DB but has activation code in Redis → Status 202 (pending)
    - Otherwise → Status 404 (not found)
    """
    try:
        logger.info(f"Activation request for device {device_id}")

        if not device_id:
            raise ValueError("Device ID header missing")

        # Check if device already exists in DB
        device_exists = await crud_device.get_device_by_mac_address(
            db=db, mac_address=device_id
        )

        if device_exists:
            # Device registered → Status 200
            logger.info(
                f"Device {device_id} already exists in DB. Activation confirmed."
            )
            return {"status": "success"}

        # Device not in DB → Check if activation data exists in Redis
        try:
            # Retrieve activation data by mac_address
            activation_data = await cache.get(CacheKey.DEVICE_ACTIVATION, device_id)

            if activation_data:
                # Activation data exists, waiting for binding
                logger.info(f"Device {device_id} has activation pending. Status 202.")
                return {
                    "status": "pending",
                    "message": "Chờ xác nhận từ user",
                }
            else:
                # No activation data found
                logger.warning(
                    f"Device {device_id} not found and no activation data in Redis"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not found and no activation data available",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving activation data for device {device_id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Activation check failed",
            )

    except ValueError as e:
        logger.warning(f"Activation validation error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activation error for device {device_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Activation error: {str(e)}",
        )
