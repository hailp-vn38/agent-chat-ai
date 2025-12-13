"""Định nghĩa các kiểu trong hệ thống công cụ"""

from enum import Enum

from dataclasses import dataclass
from typing import Any, Dict, Optional


class ToolType(Enum):
    """Liệt kê các loại công cụ"""

    SERVER_PLUGIN = "server_plugin"  # Plugin phía máy chủ
    SERVER_MCP = "server_mcp"  # MCP phía máy chủ
    DEVICE_IOT = "device_iot"  # IoT phía thiết bị
    DEVICE_MCP = "device_mcp"  # MCP phía thiết bị
    MCP_ENDPOINT = "mcp_endpoint"  # Điểm kết nối MCP


@dataclass
class ToolDefinition:
    """Định nghĩa công cụ"""

    name: str  # Tên công cụ
    description: Dict[str, Any]  # Mô tả công cụ (dạng hàm gọi của OpenAI)
    tool_type: ToolType  # Loại công cụ
    parameters: Optional[Dict[str, Any]] = None  # Tham số bổ sung
