"""
System MCP config endpoints - Server-level MCP configuration management.

Provides read-only access to system MCP servers defined in mcp_server_settings.json.
These servers are available to all users but cannot be edited through API.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.logger import get_logger
from ...schemas.base import SuccessResponse
from ...schemas.server_mcp_config import (
    ServerMCPConfigTestResponse,
    ConfigMCPServerRead,
)
from ...services.config_mcp_loader import ConfigMCPLoader
from ...services.mcp_config_tester import MCPConfigTester

router = APIRouter(tags=["system-mcp"], prefix="/system/mcp-servers")

logger = get_logger(__name__)


@router.get("", response_model=SuccessResponse[list[ConfigMCPServerRead]])
async def list_system_mcp_servers(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    List all system MCP servers from configuration file.

    Returns list of MCP servers defined in mcp_server_settings.json.
    These servers are read-only and available to all users.
    """
    try:
        logger.debug(f"Listing system MCP servers for user {current_user['id']}")

        servers = ConfigMCPLoader.get_all_servers()

        # Convert to response format
        result = [
            ConfigMCPServerRead(
                name=srv["name"],
                type=srv.get("type", "stdio"),
                description=srv.get("description"),
                source="config",
                is_active=True,
                url=srv.get("url"),
                command=srv.get("command"),
            )
            for srv in servers
        ]

        logger.info(f"Found {len(result)} system MCP servers")
        return SuccessResponse(data=result)

    except Exception as e:
        logger.error(f"Error listing system MCP servers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{server_name}", response_model=SuccessResponse[ConfigMCPServerRead])
async def get_system_mcp_server(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    server_name: Annotated[str, Path(description="MCP server name from config")],
) -> dict[str, Any]:
    """
    Get a specific system MCP server by name.

    Returns the MCP server configuration if found.
    """
    try:
        logger.debug(f"Getting system MCP server: {server_name}")

        server = ConfigMCPLoader.get_server(server_name)

        if not server:
            raise HTTPException(
                status_code=404,
                detail=f"System MCP server '{server_name}' not found",
            )

        result = ConfigMCPServerRead(
            name=server["name"],
            type=server.get("type", "stdio"),
            description=server.get("description"),
            source="config",
            is_active=True,
            url=server.get("url"),
            command=server.get("command"),
        )

        return SuccessResponse(data=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting system MCP server: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{server_name}/test", response_model=ServerMCPConfigTestResponse)
async def test_system_mcp_server(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    server_name: Annotated[str, Path(description="MCP server name from config")],
) -> dict[str, Any]:
    """
    Test connection to a system MCP server.

    Attempts to connect to the MCP server and retrieve its available tools.
    Returns test result with tools list or error message.
    """
    try:
        logger.debug(f"Testing system MCP server: {server_name}")

        server = ConfigMCPLoader.get_server(server_name)

        if not server:
            raise HTTPException(
                status_code=404,
                detail=f"System MCP server '{server_name}' not found",
            )

        # Create a mock config object for testing
        # MCPConfigTester expects an object with specific attributes
        class ConfigMock:
            def __init__(self, srv: dict):
                self.name = srv["name"]
                self.type = srv.get("type", "stdio")
                self.url = srv.get("url")
                self.command = srv.get("command")
                self.args = srv.get("args")
                self.env = srv.get("env")
                self.headers = srv.get("headers")

        mock_config = ConfigMock(server)

        # Test connection
        result = await MCPConfigTester.test_config(mock_config)

        logger.info(
            f"System MCP server test result for {server_name}: success={result.get('success')}"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing system MCP server: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reload", response_model=SuccessResponse[dict])
async def reload_system_mcp_config(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Reload system MCP configuration from file.

    Clears the cache and reloads mcp_server_settings.json.
    Useful when the config file has been updated.
    """
    try:
        logger.info(f"Reloading system MCP config by user {current_user['id']}")

        # Clear cache
        ConfigMCPLoader.clear_cache()

        # Force reload
        servers = ConfigMCPLoader.load_config(force_reload=True)

        return SuccessResponse(
            data={
                "message": "System MCP config reloaded successfully",
                "servers_count": len(servers),
                "server_names": list(servers.keys()),
            }
        )

    except Exception as e:
        logger.error(f"Error reloading system MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
