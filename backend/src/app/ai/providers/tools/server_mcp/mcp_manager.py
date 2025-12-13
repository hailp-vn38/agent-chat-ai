"""Trình quản lý MCP phía máy chủ"""

from __future__ import annotations
import asyncio
import os
import json
from typing import TYPE_CHECKING, Dict, Any, List
from app.core.logger import setup_logging
from .mcp_client import ServerMCPClient

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime

TAG = __name__
logger = setup_logging()


class ServerMCPManager:
    """Bộ quản lý tập trung cho nhiều dịch vụ MCP phía máy chủ"""

    def __init__(self, conn: ConnectionHandler) -> None:
        """Khởi tạo bộ quản lý MCP"""
        self.conn = conn
        # Lazy import để tránh circular dependency
        from app.ai.utils.paths import get_mcp_server_settings_file

        # Sử dụng đường dẫn tệp chuẩn hóa
        self.config_path = str(get_mcp_server_settings_file())

        if not os.path.exists(self.config_path):
            self.config_path = ""
            logger.bind(tag=TAG).warning(
                f"Vui lòng kiểm tra cấu hình dịch vụ MCP: {get_mcp_server_settings_file()}"
            )
        self.clients: Dict[str, ServerMCPClient] = {}
        self.tools = []

        # Get MCP selection mode and configs from agent (preloaded by crud_agent)
        self.mcp_selection_mode: str = "all"
        self.user_mcp_configs: List[Dict[str, Any]] = []
        if hasattr(conn, "agent") and conn.agent:
            self.mcp_selection_mode = conn.agent.get("mcp_selection_mode", "all")
            self.user_mcp_configs = conn.agent.get("mcp_configs", [])
            logger.bind(tag=TAG).info(
                f"MCP selection mode: {self.mcp_selection_mode}, "
                f"user configs: {len(self.user_mcp_configs)}"
            )
            if self.user_mcp_configs:
                logger.bind(tag=TAG).debug(f"User MCP configs: {self.user_mcp_configs}")

    def load_config(self) -> Dict[str, Any]:
        """
        Nạp cấu hình dịch vụ MCP dựa trên mcp_selection_mode.

        Mode "all": Load cả user configs (DB) và system configs (JSON file)
        Mode "selected": Chỉ load các MCP đã được chọn (từ user_mcp_configs)

        Returns:
            Dict với format {name: config}
        """
        merged_configs: Dict[str, Any] = {}

        if self.mcp_selection_mode == "selected":
            # Mode "selected": Chỉ dùng user MCP configs đã chọn
            if self.user_mcp_configs:
                logger.bind(tag=TAG).info(
                    f"Mode 'selected': Using {len(self.user_mcp_configs)} selected MCP configs"
                )
                for cfg in self.user_mcp_configs:
                    merged_configs[cfg["name"]] = cfg
            else:
                logger.bind(tag=TAG).debug("Mode 'selected': No MCP configs selected")
            return merged_configs

        # Mode "all": Merge cả 2 nguồn
        # Source 1: Load from config file (mcp_server_settings.json)
        if self.config_path:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                servers = config.get("mcpServers", {})
                if servers:
                    logger.bind(tag=TAG).info(
                        f"Mode 'all': Loaded {len(servers)} MCP servers from config file"
                    )
                    # Add source marker for config-based MCPs
                    for name, srv_config in servers.items():
                        srv_config["source"] = "config"
                        merged_configs[name] = srv_config
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Error loading MCP config from {self.config_path}: {e}"
                )

        # Source 2: User MCP configs from database (override if same name)
        if self.user_mcp_configs:
            logger.bind(tag=TAG).info(
                f"Mode 'all': Adding {len(self.user_mcp_configs)} user MCP configs from database"
            )
            for cfg in self.user_mcp_configs:
                # User configs override config file on name conflicts
                merged_configs[cfg["name"]] = cfg

        if merged_configs:
            logger.bind(tag=TAG).info(
                f"Total MCP configs: {len(merged_configs)} (names: {list(merged_configs.keys())})"
            )
        else:
            logger.bind(tag=TAG).debug("No MCP configs available")

        return merged_configs

    async def initialize_servers(self) -> None:
        """Khởi tạo tất cả dịch vụ MCP"""
        config = self.load_config()
        for name, srv_config in config.items():
            if not srv_config.get("command") and not srv_config.get("url"):
                logger.bind(tag=TAG).warning(
                    f"Skipping server {name}: neither command nor url specified"
                )
                continue

            try:
                # Khởi tạo client MCP phía máy chủ
                logger.bind(tag=TAG).info(f"Khởi tạo client MCP phía máy chủ: {name}")
                client = ServerMCPClient(srv_config)
                await client.initialize()
                self.clients[name] = client
                client_tools = client.get_available_tools()
                self.tools.extend(client_tools)

            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Failed to initialize MCP server {name}: {e}"
                )

        # Xuất danh sách công cụ MCP phía máy chủ đang hỗ trợ
        if hasattr(self.conn, "func_handler") and self.conn.func_handler:
            # Làm mới bộ nhớ đệm để chắc chắn công cụ MCP được nạp
            if hasattr(self.conn.func_handler, "tool_manager"):
                self.conn.func_handler.tool_manager.refresh_tools()
            self.conn.func_handler.current_support_functions()

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Lấy định nghĩa hàm của mọi công cụ"""
        return self.tools

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Kiểm tra xem có phải công cụ MCP hay không"""
        for tool in self.tools:
            if (
                tool.get("function") is not None
                and tool["function"].get("name") == tool_name
            ):
                return True
        return False

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Thực thi công cụ, nếu thất bại sẽ thử kết nối lại"""
        logger.bind(tag=TAG).debug(
            f"Thực thi công cụ MCP phía máy chủ {tool_name}, tham số: {arguments}"
        )

        max_retries = 3  # Số lần thử tối đa
        retry_interval = 2  # Thời gian chờ giữa các lần thử (giây)

        # Tìm client tương ứng
        client_name = None
        target_client = None
        for name, client in self.clients.items():
            if client.has_tool(tool_name):
                client_name = name
                target_client = client
                break

        if not target_client:
            raise ValueError(
                f"Không tìm thấy công cụ {tool_name} trong bất kỳ dịch vụ MCP nào"
            )

        # Gọi công cụ với cơ chế thử lại
        for attempt in range(max_retries):
            try:
                return await target_client.call_tool(tool_name, arguments)
            except Exception as e:
                # Nếu lần thử cuối cùng thất bại thì ném lỗi luôn
                if attempt == max_retries - 1:
                    raise

                logger.bind(tag=TAG).warning(
                    f"Thực thi công cụ {tool_name} thất bại (lần {attempt+1}/{max_retries}): {e}"
                )

                # Thử kết nối lại
                logger.bind(tag=TAG).info(
                    f"Trước khi thử lại, kết nối lại client MCP {client_name}"
                )
                try:
                    # Đóng kết nối cũ
                    await target_client.cleanup()

                    # Khởi tạo lại client
                    config = self.load_config()
                    if client_name in config:
                        client = ServerMCPClient(config[client_name])
                        await client.initialize()
                        self.clients[client_name] = client
                        target_client = client
                        logger.bind(tag=TAG).info(
                            f"Tái kết nối client MCP thành công: {client_name}"
                        )
                    else:
                        logger.bind(tag=TAG).error(
                            f"Cannot reconnect MCP client {client_name}: config not found"
                        )
                except Exception as reconnect_error:
                    logger.bind(tag=TAG).error(
                        f"Failed to reconnect MCP client {client_name}: {reconnect_error}"
                    )

                # Đợi một khoảng rồi thử lại
                await asyncio.sleep(retry_interval)

    async def cleanup_all(self) -> None:
        """Đóng tất cả client MCP"""
        for name, client in list(self.clients.items()):
            try:
                if hasattr(client, "cleanup"):
                    await asyncio.wait_for(client.cleanup(), timeout=20)
                logger.bind(tag=TAG).info(f"Client MCP phía máy chủ đã đóng: {name}")
            except (asyncio.TimeoutError, Exception) as e:
                logger.bind(tag=TAG).error(
                    f"Lỗi khi đóng client MCP phía máy chủ {name}: {e}"
                )
        self.clients.clear()
