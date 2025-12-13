"""
MCP configuration tester service.

Tests MCP server connections and retrieves available tools.
"""

import asyncio
import logging
from typing import Optional

from ..schemas.server_mcp_config import (
    ServerMCPConfigRead,
    ServerMCPConfigTestResponse,
    MCPToolInfo,
    TransportTypeEnum,
)


logger = logging.getLogger(__name__)


class MCPConfigTester:
    """Service for testing MCP server configurations."""

    # Connection timeout in seconds
    DEFAULT_TIMEOUT = 10

    @staticmethod
    async def test_config(
        config: ServerMCPConfigRead,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict:
        """Test MCP server connection and get tools.

        Args:
            config: MCP configuration to test (ServerMCPConfigRead or ServerMCPConfigCreate)
            timeout: Connection timeout in seconds

        Returns:
            Dict with success status, name, and tools or error
        """
        try:
            # Import here to avoid circular imports
            from ..ai.providers.tools.server_mcp.mcp_client import ServerMCPClient

            # Support both ServerMCPConfigRead and ServerMCPConfigCreate
            # Extract name for response
            config_name = getattr(config, "name", "unknown")

            # Create temporary MCP client
            # Only include fields that have values to match ServerMCPClient's
            # detection logic (checks "command" in config or "url" in config)
            config_dict: dict = {}

            # Stdio transport fields
            if hasattr(config, "command") and config.command:
                config_dict["command"] = config.command
                config_dict["args"] = config.args or []
                config_dict["env"] = config.env or {}

            # SSE/HTTP transport fields
            if hasattr(config, "url") and config.url:
                config_dict["url"] = config.url
                config_dict["headers"] = config.headers or {}
                # Map type to transport for streamable-http
                if hasattr(config, "type") and config.type == TransportTypeEnum.HTTP:
                    config_dict["transport"] = "streamable-http"

            if not config_dict:
                return {
                    "success": False,
                    "message": "Invalid config: must have either 'command' or 'url'",
                    "name": config_name,
                    "error": "invalid_config",
                }

            client = ServerMCPClient(config=config_dict)

            # Test connection with timeout
            try:
                await asyncio.wait_for(
                    client.initialize(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "message": f"Connection timeout after {timeout} seconds",
                    "name": config_name,
                    "error": "timeout",
                }
            except Exception as init_error:
                # Handle initialization errors (404, session terminated, etc.)
                error_msg = str(init_error)
                if "404" in error_msg or "Not Found" in error_msg:
                    message = (
                        "MCP server endpoint not found (404). Please check the URL."
                    )
                elif "Session terminated" in error_msg:
                    message = "MCP server session terminated unexpectedly. The server may not be a valid MCP endpoint."
                elif "Connection refused" in error_msg:
                    message = "Connection refused. The server is not reachable."
                else:
                    message = f"Failed to initialize MCP connection: {error_msg}"

                return {
                    "success": False,
                    "message": message,
                    "name": config_name,
                    "error": error_msg,
                }

            # Get available tools from client.tools_dict
            try:
                tool_list = [
                    {
                        "name": name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for name, tool in client.tools_dict.items()
                ]

                return {
                    "success": True,
                    "message": f"Connection successful, found {len(tool_list)} tools",
                    "name": config_name,
                    "tools": tool_list,
                    "error": None,
                }

            except Exception as e:
                logger.warning(f"Failed to get tools from {config_name}: {str(e)}")
                return {
                    "success": True,
                    "message": "Connection successful but could not retrieve tools",
                    "name": config_name,
                    "tools": [],
                    "error": None,
                }

        except Exception as e:
            # Get name for error logging
            config_name = getattr(config, "name", "unknown")

            logger.error(f"Failed to test MCP config {config_name}: {str(e)}")
            return {
                "success": False,
                "message": "Connection failed",
                "name": config_name,
                "error": str(e),
            }

        finally:
            # Cleanup - suppress all cleanup errors as they don't affect test result
            try:
                if "client" in locals() and client:
                    # Suppress cleanup errors by wrapping in try-except
                    try:
                        await asyncio.wait_for(client.cleanup(), timeout=5)
                    except (asyncio.TimeoutError, Exception):
                        # Silently ignore cleanup errors - test already completed
                        pass
            except Exception:
                # Final safety net - ignore any cleanup issues
                pass
