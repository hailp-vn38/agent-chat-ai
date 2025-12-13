"""Định nghĩa lớp cơ sở cho bộ thực thi công cụ"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Any
from .tool_types import ToolDefinition
from app.ai.plugins_func.register import ActionResponse
if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler  # chỉ dùng cho hint, không chạy lúc runtime


class ToolExecutor(ABC):
    """Lớp trừu tượng cho bộ thực thi công cụ"""

    @abstractmethod
    async def execute(
        self, conn: ConnectionHandler, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """Thực thi lời gọi công cụ"""
        pass

    @abstractmethod
    def get_tools(self) -> Dict[str, ToolDefinition]:
        """Lấy tất cả công cụ do bộ thực thi quản lý"""
        pass

    @abstractmethod
    def has_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có công cụ cụ thể hay không"""
        pass
