"""
Agent MCP selection endpoints.

Allows agents to select specific MCP servers (user-defined or config-based).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.logger import get_logger
from ...crud.crud_agent import crud_agent
from ...crud.crud_server_mcp_config import crud_server_mcp_config
from ...schemas.agent import (
    AgentRead,
    MCPSelection,
    MCPServerReference,
    AgentMCPSelectionRead,
)
from ...schemas.base import SuccessResponse
from ...schemas.server_mcp_config import (
    ServerMCPConfigRead,
    MCPListItem,
    MCPSourceFilter,
)
from ...services.agent_mcp_selection_service import AgentMCPSelectionService
from ...services.mcp_reference_validator import MCPReferenceValidator
from ...services.config_mcp_loader import ConfigMCPLoader

router = APIRouter(tags=["agent-mcp"], prefix="/agents/{agent_id}/mcp")

logger = get_logger(__name__)


@router.get("", response_model=SuccessResponse[AgentMCPSelectionRead])
async def get_agent_mcp_selection(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    agent_id: str,
) -> SuccessResponse[AgentMCPSelectionRead]:
    """
    Get current MCP server selection configuration for an agent.

    Returns complete selection data with all metadata in single query.
    Includes staleness warnings if metadata is outdated.
    """
    try:
        logger.debug(f"Getting MCP selection for agent {agent_id}")

        selection = await AgentMCPSelectionService.get_selection(
            agent_id=agent_id,
            user_id=current_user["id"],
            db=db,
        )

        logger.debug(f"Successfully retrieved MCP selection for agent {agent_id}")
        return SuccessResponse(data=selection)

    except NotFoundException:
        logger.warning(f"Agent {agent_id} not found for user {current_user['id']}")
        raise HTTPException(status_code=404, detail="Agent not found")
    except Exception as e:
        logger.error(f"Error getting agent MCP selection: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("", response_model=SuccessResponse[AgentMCPSelectionRead])
async def update_agent_mcp_selection(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    agent_id: str,
    selection: MCPSelection,
) -> SuccessResponse[AgentMCPSelectionRead]:
    """
    Update MCP server selection for an agent.

    Allows switching between 'all' servers mode and 'selected' servers mode.
    When mode is 'selected', provide a list of MCP server references.

    Reference format:
    - db:{uuid} - User-defined MCP server
    - config:{name} - System MCP server from config.yml

    Atomically validates and resolves all references before persisting.
    """
    try:
        logger.debug(
            f"Updating MCP selection for agent {agent_id}, mode={selection.mode}"
        )

        updated = await AgentMCPSelectionService.update_selection(
            agent_id=agent_id,
            user_id=current_user["id"],
            selection=selection,
            db=db,
        )

        logger.info(f"Successfully updated MCP selection for agent {agent_id}")
        return SuccessResponse(data=updated)

    except NotFoundException:
        logger.warning(f"Agent {agent_id} not found for user {current_user['id']}")
        raise HTTPException(status_code=404, detail="Agent not found")
    except ValueError as e:
        logger.warning(f"Validation error updating agent MCP selection: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating agent MCP selection: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/available", response_model=SuccessResponse[dict])
async def get_available_mcp_servers(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    agent_id: str,
    source: Annotated[MCPSourceFilter, Query()] = MCPSourceFilter.ALL,
) -> dict[str, Any]:
    """
    Get all available MCP servers for the current user.

    Returns list of MCP servers from:
    - User-defined servers (from database)
    - System servers (from config.yml)

    Each server includes reference format for selection.
    """
    try:
        logger.debug(
            f"Getting available MCP servers for user {current_user['id']}, source={source}"
        )

        mcp_servers = []

        # Get user's MCP servers
        if source in (MCPSourceFilter.ALL, MCPSourceFilter.USER):
            configs_data = await crud_server_mcp_config.get_multi(
                db=db,
                user_id=current_user["id"],
                is_active=True,
                is_deleted=False,
                schema_to_select=ServerMCPConfigRead,
            )

            for config in configs_data.get("data", []):
                # Convert to model if needed
                if isinstance(config, dict):
                    config_dict = config
                else:
                    config_dict = (
                        config.model_dump()
                        if hasattr(config, "model_dump")
                        else dict(config)
                    )

                mcp_servers.append(
                    MCPListItem(
                        reference=f"db:{config_dict['id']}",
                        name=config_dict["name"],
                        description=config_dict.get("description"),
                        type=config_dict["type"],
                        source="user",
                        permissions=["read", "test", "edit", "delete"],
                        is_active=config_dict.get("is_active", True),
                        id=config_dict["id"],
                        user_id=config_dict["user_id"],
                        created_at=config_dict.get("created_at"),
                        updated_at=config_dict.get("updated_at"),
                    ).model_dump()
                )

        # Get config MCP servers
        if source in (MCPSourceFilter.ALL, MCPSourceFilter.CONFIG):
            config_servers = ConfigMCPLoader.get_all_servers()
            for server_config in config_servers:
                mcp_servers.append(
                    MCPListItem(
                        reference=f"config:{server_config['name']}",
                        name=server_config["name"],
                        description=server_config.get("description"),
                        type=server_config.get("type", "stdio"),
                        source="config",
                        permissions=["read", "test"],  # Config servers are read-only
                        is_active=True,
                    ).model_dump()
                )

        return SuccessResponse(
            data={
                "agent_id": agent_id,
                "mcp_servers": mcp_servers,
                "total": len(mcp_servers),
                "source_filter": source.value,
            }
        )

    except Exception as e:
        logger.error(f"Error getting available MCP servers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
