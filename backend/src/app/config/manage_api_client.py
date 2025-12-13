import os
import time
import base64
from typing import Dict, Optional

import httpx

TAG = __name__


class DeviceNotFoundException(Exception):
    pass


class DeviceBindException(Exception):
    def __init__(self, bind_code):
        self.bind_code = bind_code
        super().__init__(f"Lỗi liên kết thiết bị, mã liên kết: {bind_code}")


class ManageApiClient:
    _instance = None
    _client = None
    _secret = None

    def __new__(cls, config):
        """Bảo đảm singleton toàn cục, cho phép truyền tham số cấu hình"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._init_client(config)
        return cls._instance

    @classmethod
    def _init_client(cls, config):
        """Khởi tạo pool kết nối được duy trì"""
        cls.config = config.get("manager-api")

        if not cls.config:
            raise Exception("Cấu hình manager-api không hợp lệ")

        if not cls.config.get("url") or not cls.config.get("secret"):
            raise Exception("Cấu hình URL hoặc secret của manager-api không hợp lệ")

        secret_value = cls.config.get("secret", "")
        # Từ chối secret chứa ký tự Trung Quốc (thường là giá trị mặc định chưa cấu hình)
        if any("\u4e00" <= ch <= "\u9fff" for ch in secret_value):
            raise Exception("Vui lòng cấu hình secret của manager-api trước")

        cls._secret = secret_value
        cls.max_retries = cls.config.get("max_retries", 6)
        cls.retry_delay = cls.config.get("retry_delay", 10)
        cls._client = httpx.Client(
            base_url=cls.config.get("url"),
            headers={
                "User-Agent": f"PythonClient/2.0 (PID:{os.getpid()})",
                "Accept": "application/json",
                "Authorization": "Bearer " + cls._secret,
            },
            timeout=cls.config.get("timeout", 30),
        )

    @classmethod
    def _request(cls, method: str, endpoint: str, **kwargs) -> Dict:
        """Gửi một yêu cầu HTTP và xử lý phản hồi"""
        endpoint = endpoint.lstrip("/")
        response = cls._client.request(method, endpoint, **kwargs)
        response.raise_for_status()

        result = response.json()

        if result.get("code") == 10041:
            raise DeviceNotFoundException(result.get("msg"))
        elif result.get("code") == 10042:
            raise DeviceBindException(result.get("msg"))
        elif result.get("code") != 0:
            raise Exception(f"Lỗi từ API: {result.get('msg', 'Lỗi không xác định')}")

        return result.get("data") if result.get("code") == 0 else None

    @classmethod
    def _should_retry(cls, exception: Exception) -> bool:
        """Xác định ngoại lệ có nên retry hay không"""
        if isinstance(
            exception, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)
        ):
            return True

        if isinstance(exception, httpx.HTTPStatusError):
            status_code = exception.response.status_code
            return status_code in [408, 429, 500, 502, 503, 504]

        return False

    @classmethod
    def _execute_request(cls, method: str, endpoint: str, **kwargs) -> Dict:
        """Trình thực thi yêu cầu có cơ chế retry"""
        retry_count = 0

        while retry_count <= cls.max_retries:
            try:
                return cls._request(method, endpoint, **kwargs)
            except Exception as exc:
                if retry_count < cls.max_retries and cls._should_retry(exc):
                    retry_count += 1
                    print(
                        f"Yêu cầu {method} {endpoint} thất bại, sẽ retry lần {retry_count} sau {cls.retry_delay:.1f} giây"
                    )
                    time.sleep(cls.retry_delay)
                    continue
                raise

    @classmethod
    def safe_close(cls):
        """Đóng pool kết nối một cách an toàn"""
        if cls._client:
            cls._client.close()
            cls._instance = None


def get_server_config() -> Optional[Dict]:
    """Lấy cấu hình cơ bản của máy chủ"""
    return ManageApiClient._instance._execute_request("POST", "/config/server-base")


def get_agent_models(
    mac_address: str, client_id: str, selected_module: Dict
) -> Optional[Dict]:
    """Lấy cấu hình mô hình đại lý"""
    return ManageApiClient._instance._execute_request(
        "POST",
        "/config/agent-models",
        json={
            "macAddress": mac_address,
            "clientId": client_id,
            "selectedModule": selected_module,
        },
    )


def save_mem_local_short(mac_address: str, short_momery: str) -> Optional[Dict]:
    try:
        # return ManageApiClient._instance._execute_request(
        #     "PUT",
        #     f"/agent/saveMemory/{mac_address}",
        #     json={
        #         "summaryMemory": short_momery,
        #     },
        # )
        return {}
    except Exception as exc:
        print(f"Lưu trí nhớ ngắn lên máy chủ thất bại: {exc}")
        return None


def report(
    mac_address: str, session_id: str, chat_type: int, content: str, audio, report_time
) -> Optional[Dict]:
    """Ví dụ phương thức nghiệp vụ có cơ chế ngắt mạch"""
    if not content or not ManageApiClient._instance:
        return None
    try:
        return ManageApiClient._instance._execute_request(
            "POST",
            "/agent/chat-history/report",
            json={
                "macAddress": mac_address,
                "sessionId": session_id,
                "chatType": chat_type,
                "content": content,
                "reportTime": report_time,
                "audioBase64": (
                    base64.b64encode(audio).decode("utf-8") if audio else None
                ),
            },
        )
    except Exception as exc:
        print(f"Báo cáo TTS thất bại: {exc}")
        return None


def init_service(config):
    ManageApiClient(config)


def manage_api_http_safe_close():
    ManageApiClient.safe_close()
