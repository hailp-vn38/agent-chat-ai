"""Authentication Manager - Port"""

import hmac
import hashlib
import base64
import time
from typing import Dict, Any, Optional, Tuple
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession


class AuthenticationError(Exception):
    """Ngoại lệ xác thực"""

    pass


class AuthManager:
    """
    Trình quản lý xác thực thống nhất
    Tạo và xác minh bộ ba client_id device_id token (HMAC-SHA256)
    token không chứa client_id/device_id dạng rõ, chỉ mang chữ ký + dấu thời gian; client_id/device_id được truyền khi kết nối
    Trong MQTT client_id: client_id, username: device_id, password: token
    Trong Websocket, header:{Device-ID: device_id, Client-ID: client_id, Authorization: Bearer token, ......}
    """

    def __init__(self, secret_key: str, expire_seconds: int = 60 * 60 * 24 * 30):
        if not expire_seconds or expire_seconds < 0:
            self.expire_seconds = 60 * 60 * 24 * 30
        else:
            self.expire_seconds = expire_seconds
        self.secret_key = secret_key

    def _sign(self, content: str) -> str:
        """Ký HMAC-SHA256 và mã hóa Base64"""
        sig = hmac.new(
            self.secret_key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")

    def generate_token(self, client_id: str, username: str) -> str:
        """
        Tạo token
        Args:
            client_id: ID kết nối của thiết bị
            username: Tên người dùng của thiết bị (thường là deviceId)
        Returns:
            str: chuỗi token
        """
        ts = int(time.time())
        content = f"{client_id}|{username}|{ts}"
        signature = self._sign(content)
        # token chỉ bao gồm chữ ký và dấu thời gian, không có dữ liệu rõ
        token = f"{signature}.{ts}"
        return token

    def verify_token(self, token: str, client_id: str, username: str) -> bool:
        """
        Xác minh tính hợp lệ của token
        Args:
            token: token do phía khách gửi
            client_id: client_id dùng khi kết nối
            username: username dùng khi kết nối
        """
        try:
            sig_part, ts_str = token.split(".")
            ts = int(ts_str)
            if int(time.time()) - ts > self.expire_seconds:
                return False  # Hết hạn

            expected_sig = self._sign(f"{client_id}|{username}|{ts}")
            if not hmac.compare_digest(sig_part, expected_sig):
                return False

            return True
        except Exception:
            return False


class DeviceAuthService:
    """
    Service xác thực device - gom device lookup + auth logic
    Luôn yêu cầu JWT device token để xác thực
    Headers fallback pattern: Headers trống → dùng query params
    """

    def __init__(self, auth_manager: Optional[AuthManager] = None):
        self.auth_manager = auth_manager
        self.logger = None

    def set_logger(self, logger):
        """Inject logger"""
        self.logger = logger

    def _merge_auth_fields(
        self, websocket: WebSocket
    ) -> Tuple[str, str, str, str, str]:
        """
        Lấy auth fields từ headers (ưu tiên), fallback to query params
        Returns: (device_id, client_id, token, client_ip, auth_header)
        """
        # Headers (ưu tiên)
        headers_dict = dict(websocket.headers.items())

        # Query params (fallback)
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

        return device_id, client_id, token, client_ip, auth_header

    async def authenticate(
        self,
        websocket: WebSocket,
    ) -> Dict[str, Any]:
        """
        Thực hiện xác thực đầy đủ:
        1. Extract auth fields từ headers/params
        2. Validate JWT device token (bắt buộc) - không dùng device_id từ header để xác thực

        Returns: auth state dict với device_info và agent nếu found
        """
        device_id, client_id, token, client_ip, _ = self._merge_auth_fields(websocket)

        auth_result = {
            "device_id": device_id,
            "device_mac": device_id,  # MAC là device_id hiện tại
            "client_id": client_id,
            "client_ip": client_ip,
            "is_authenticated": False,
            "auth_error": None,
        }

        # Validate required fields
        if not client_id or not token:
            auth_result["auth_error"] = (
                "Missing required auth fields (client-id, token)"
            )
            if self.logger:
                self.logger.bind(tag="DeviceAuthService").warning(
                    f"Missing auth fields: "
                    f"client_id={bool(client_id)}, token={bool(token)}"
                )
            return auth_result

        # Verify JWT device token (token contains device_id)
        try:
            from app.core.security import verify_device_token

            token_data = await verify_device_token(token)
            self.logger.bind(tag="DeviceAuthService").debug(
                f"JWT device token data: {token_data}"
            )
            if token_data and token_data.device_id:
                auth_result["is_authenticated"] = True
                auth_result["device_id"] = token_data.device_id
                if self.logger:
                    self.logger.bind(tag="DeviceAuthService").debug(
                        f"JWT device token verified for: {token_data.device_id}"
                    )
            else:
                auth_result["auth_error"] = "JWT token verification failed"
                if self.logger:
                    self.logger.bind(tag="DeviceAuthService").warning(
                        f"JWT token invalid or expired"
                    )
                return auth_result
        except Exception as exc:
            auth_result["auth_error"] = f"Auth verification error: {exc}"
            if self.logger:
                self.logger.bind(tag="DeviceAuthService").error(
                    f"Auth verification error: {exc}"
                )
            return auth_result

        return auth_result

    async def invalidate_device_cache(self, mac_address: str) -> None:
        """
        Invalidate device info cache
        Call khi device info bị update
        """
        try:
            from app.core.utils.cache import CacheKey, get_cache_manager

            cache_manager = get_cache_manager()
            await cache_manager.delete(CacheKey.DEVICE_BY_MAC, mac_address)
            if self.logger:
                self.logger.bind(tag="DeviceAuthService").debug(
                    f"Device info cache invalidated: {mac_address}"
                )
        except Exception as e:
            if self.logger:
                self.logger.bind(tag="DeviceAuthService").warning(
                    f"Cache invalidation error: {e}"
                )


class DeviceNotFoundException(Exception):
    """Exception khi device không tìm thấy"""

    pass
