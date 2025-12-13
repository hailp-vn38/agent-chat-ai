"""Client MCP phía máy chủ"""

from __future__ import annotations

from datetime import timedelta
import asyncio
import os
import shutil
import concurrent.futures
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from app.core.logger import setup_logging
from app.ai.utils.util import sanitize_tool_name

TAG = __name__


class ServerMCPClient:
    """Client MCP phía máy chủ để kết nối và quản lý dịch vụ MCP"""

    def __init__(self, config: Dict[str, Any]):
        """Khởi tạo client MCP phía máy chủ

        Args:
            config: Từ điển cấu hình dịch vụ MCP
        """
        self.logger = setup_logging()
        self.config = config

        self._worker_task: Optional[asyncio.Task] = None
        self._ready_evt = asyncio.Event()
        self._shutdown_evt = asyncio.Event()

        self.session: Optional[ClientSession] = None
        self.tools: List = []  # Đối tượng công cụ gốc
        self.tools_dict: Dict[str, Any] = {}
        self.name_mapping: Dict[str, str] = {}

    async def initialize(self):
        """Khởi tạo kết nối client MCP"""
        if self._worker_task:
            return

        self._worker_task = asyncio.create_task(
            self._worker(), name="ServerMCPClientWorker"
        )
        await self._ready_evt.wait()

        self.logger.bind(tag=TAG).info(
            f"Client MCP phía máy chủ đã kết nối, công cụ khả dụng: {[name for name in self.name_mapping.values()]}"
        )

    async def cleanup(self):
        """Giải phóng tài nguyên client MCP"""
        if not self._worker_task:
            return

        self._shutdown_evt.set()
        try:
            await asyncio.wait_for(self._worker_task, timeout=20)
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.bind(tag=TAG).error(
                f"Lỗi khi đóng client MCP phía máy chủ: {e}"
            )
        finally:
            self._worker_task = None

    def has_tool(self, name: str) -> bool:
        """Kiểm tra xem có chứa công cụ chỉ định hay không

        Args:
            name: Tên công cụ

        Returns:
            bool: Có chứa công cụ hay không
        """
        return name in self.tools_dict

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Lấy định nghĩa của mọi công cụ khả dụng

        Returns:
            List[Dict[str, Any]]: Danh sách định nghĩa công cụ
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for name, tool in self.tools_dict.items()
        ]

    async def call_tool(self, name: str, args: dict) -> Any:
        """Gọi công cụ cụ thể

        Args:
            name: Tên công cụ
            args: Tham số của công cụ

        Returns:
            Any: Kết quả thực thi công cụ

        Raises:
            RuntimeError: Ném khi client chưa được khởi tạo
        """
        if not self.session:
            raise RuntimeError("Client MCP phía máy chủ chưa được khởi tạo")

        real_name = self.name_mapping.get(name, name)
        loop = self._worker_task.get_loop()
        coro = self.session.call_tool(real_name, args)

        if loop is asyncio.get_running_loop():
            return await coro

        fut: concurrent.futures.Future = asyncio.run_coroutine_threadsafe(coro, loop)
        return await asyncio.wrap_future(fut)

    def is_connected(self) -> bool:
        """Kiểm tra client MCP có kết nối ổn định không

        Returns:
            bool: True nếu client đã kết nối và hoạt động bình thường, ngược lại False
        """
        # Kiểm tra nhiệm vụ nền có tồn tại không
        if self._worker_task is None:
            return False

        # Kiểm tra nhiệm vụ đã hoàn thành/hủy chưa
        if self._worker_task.done():
            return False

        # Kiểm tra phiên làm việc có tồn tại không
        if self.session is None:
            return False

        # Mọi kiểm tra đều hợp lệ, kết nối bình thường
        return True

    async def _worker(self):
        """Coroutine nền của client MCP"""
        async with AsyncExitStack() as stack:
            try:
                self.logger.bind(tag=TAG).debug(
                    f"Bắt đầu kết nối MCP: {self.config.get('name', 'unknown')}, config keys: {list(self.config.keys())}"
                )

                # Thiết lập StdioClient
                if "command" in self.config:
                    self.logger.bind(tag=TAG).debug(
                        f"Sử dụng stdio transport, command: {self.config['command']}"
                    )
                    cmd = (
                        shutil.which("npx")
                        if self.config["command"] == "npx"
                        else self.config["command"]
                    )
                    env = {**os.environ, **(self.config.get("env") or {})}
                    params = StdioServerParameters(
                        command=cmd,
                        args=self.config.get("args") or [],
                        env=env,
                    )
                    stdio_r, stdio_w = await stack.enter_async_context(
                        stdio_client(params)
                    )
                    read_stream, write_stream = stdio_r, stdio_w

                # Thiết lập SSEClient
                elif "url" in self.config:
                    self.logger.bind(tag=TAG).debug(
                        f"Sử dụng HTTP transport, url: {self.config['url']}"
                    )
                    headers = dict(self.config.get("headers") or {})
                    if "API_ACCESS_TOKEN" in self.config:
                        headers["Authorization"] = (
                            f"Bearer {self.config['API_ACCESS_TOKEN']}"
                        )
                        self.logger.bind(tag=TAG).warning(
                            "Bạn đang dùng cấu hình API_ACCESS_TOKEN đã lỗi thời, hãy đặt trực tiếp vào headers trong .mcp_server_settings.json, ví dụ 'Authorization': 'Bearer API_ACCESS_TOKEN'"
                        )
                    transport_type = self.config.get("transport", "sse")
                    self.logger.bind(tag=TAG).debug(f"Transport type: {transport_type}")

                    if transport_type == "streamable-http" or transport_type == "http":
                        # 使用 Streamable HTTP 传输
                        try:
                            self.logger.bind(tag=TAG).debug(
                                f"Đang kết nối streamable-http đến {self.config['url']}..."
                            )
                            result = await stack.enter_async_context(
                                streamablehttp_client(
                                    url=self.config["url"],
                                    headers=headers,
                                    timeout=self.config.get("timeout", 30),
                                    sse_read_timeout=self.config.get(
                                        "sse_read_timeout", 60 * 5
                                    ),
                                    terminate_on_close=self.config.get(
                                        "terminate_on_close", True
                                    ),
                                )
                            )
                            self.logger.bind(tag=TAG).debug(
                                f"streamablehttp_client result type: {type(result)}, result: {result}"
                            )
                            if result is None:
                                raise ValueError(
                                    f"streamablehttp_client trả về None cho URL: {self.config['url']}"
                                )
                            http_r, http_w, get_session_id = result
                            self.logger.bind(tag=TAG).debug(
                                f"http_r: {type(http_r)}, http_w: {type(http_w)}"
                            )
                            if http_r is None or http_w is None:
                                raise ValueError(
                                    f"streamablehttp_client: read/write stream là None cho URL: {self.config['url']}"
                                )
                            read_stream, write_stream = http_r, http_w
                        except Exception as e:
                            self.logger.bind(tag=TAG).error(
                                f"Lỗi kết nối streamable-http đến {self.config['url']}: {e}"
                            )
                            raise
                    else:
                        # 使用传统的 SSE 传输
                        self.logger.bind(tag=TAG).debug(
                            f"Đang kết nối SSE đến {self.config['url']}..."
                        )
                        sse_r, sse_w = await stack.enter_async_context(
                            sse_client(
                                url=self.config["url"],
                                headers=headers,
                                timeout=self.config.get("timeout", 5),
                                sse_read_timeout=self.config.get(
                                    "sse_read_timeout", 60 * 5
                                ),
                            )
                        )
                        read_stream, write_stream = sse_r, sse_w

                else:
                    raise ValueError(
                        "Cấu hình client MCP phải chứa 'command' hoặc 'url'"
                    )

                self.logger.bind(tag=TAG).debug(
                    f"Tạo ClientSession với read_stream: {type(read_stream)}, write_stream: {type(write_stream)}"
                )
                self.session = await stack.enter_async_context(
                    ClientSession(
                        read_stream=read_stream,
                        write_stream=write_stream,
                        read_timeout_seconds=timedelta(seconds=15),
                    )
                )
                self.logger.bind(tag=TAG).debug("Đang initialize session...")
                await self.session.initialize()
                self.logger.bind(tag=TAG).debug("Session initialized thành công")

                # Lấy danh sách công cụ
                self.logger.bind(tag=TAG).debug("Đang list_tools()...")
                tools_result = await self.session.list_tools()
                # self.logger.bind(tag=TAG).debug(
                #     f"tools_result type: {type(tools_result)}, tools_result: {tools_result}"
                # )
                self.tools = (
                    tools_result.tools if tools_result and tools_result.tools else []
                )
                self.logger.bind(tag=TAG).debug(f"Số tools: {len(self.tools)}")
                for t in self.tools:
                    sanitized = sanitize_tool_name(t.name)
                    self.tools_dict[sanitized] = t
                    self.name_mapping[sanitized] = t.name

                self._ready_evt.set()

                # Chờ tín hiệu đóng
                await self._shutdown_evt.wait()

            except Exception as e:
                self.logger.bind(tag=TAG).error(
                    f"Lỗi coroutine client MCP phía máy chủ: {e}"
                )
                self._ready_evt.set()
                raise
