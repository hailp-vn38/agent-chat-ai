"""
MCP config endpoints - User-scoped MCP server management.

Allows users to create, read, update, delete, and test MCP server configurations.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import NotFoundException
from ...core.logger import get_logger
from ...crud.crud_server_mcp_config import crud_server_mcp_config
from ...schemas.base import PaginatedResponse, SuccessResponse
from ...schemas.server_mcp_config import (
    ServerMCPConfigCreate,
    ServerMCPConfigCreateInternal,
    ServerMCPConfigRead,
    ServerMCPConfigUpdate,
    ServerMCPConfigTestResponse,
    ServerMCPConfigRefreshResponse,
)
from ...services.mcp_config_validator import MCPConfigValidator
from ...services.mcp_config_tester import MCPConfigTester
from ...services.tools_comparator import ToolsComparator

router = APIRouter(tags=["mcp-configs"], prefix="/users/me/mcp-configs")

logger = get_logger(__name__)

# Constants
MAX_MCP_CONFIGS_PER_USER = 10


@router.post("/test-raw", response_model=ServerMCPConfigTestResponse)
async def test_raw_mcp_config(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    config: ServerMCPConfigCreate,
) -> dict[str, Any]:
    """
    Test a raw MCP configuration without saving to database.

    Allows users to validate their MCP server config and see available tools
    before creating the configuration in the database.

    Returns test result with tools or error message.
    """
    try:
        logger.debug(
            f"Testing raw MCP config for user {current_user['id']}: {config.name}"
        )

        # Validate configuration format
        MCPConfigValidator.validate_config(config)

        # Test connection - returns dict with name, display_name, tools
        result = await MCPConfigTester.test_config(config)

        # Return test result directly (no SuccessResponse wrapper)
        return result

    except ValueError as e:
        logger.warning(f"Validation error testing raw MCP config: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error testing raw MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=SuccessResponse[ServerMCPConfigRead], status_code=201)
async def create_mcp_config(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config: ServerMCPConfigCreate,
) -> dict[str, Any]:
    """
    Create a new MCP server configuration for the current user.

    Returns the created `ServerMCPConfigRead` on success (status 201).
    """
    try:
        logger.debug(
            f"Creating MCP config for user {current_user['id']}: {config.name}"
        )

        # Validate configuration
        MCPConfigValidator.validate_config(config)

        # Check user config limit
        existing_configs = await crud_server_mcp_config.get_multi(
            db=db,
            user_id=current_user["id"],
            is_deleted=False,
        )

        if len(existing_configs.get("data", [])) >= MAX_MCP_CONFIGS_PER_USER:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_MCP_CONFIGS_PER_USER} MCP configs per user",
            )

        # Prepare data for create
        from datetime import datetime, timezone

        create_data = config.model_dump()
        create_data["user_id"] = current_user["id"]

        # Set tools_last_synced_at if tools are provided
        if config.tools is not None:
            create_data["tools_last_synced_at"] = datetime.now(timezone.utc)

        # Create config
        db_config = await crud_server_mcp_config.create(
            db=db,
            object=ServerMCPConfigCreateInternal(**create_data),
            schema_to_select=ServerMCPConfigRead,
        )

        return SuccessResponse(data=db_config)

    except ValueError as e:
        logger.warning(f"Validation error creating MCP config: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=PaginatedResponse[ServerMCPConfigRead])
async def list_mcp_configs(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    is_active: Annotated[bool | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """
    List all MCP configurations for the current user (paginated).

    Returns a `PaginatedResponse[ServerMCPConfigRead]`.
    """
    try:
        logger.debug(f"Listing MCP configs for user {current_user['id']}")

        # Build filters
        filters = {
            "user_id": current_user["id"],
            "is_deleted": False,
        }
        if is_active is not None:
            filters["is_active"] = is_active
        if type is not None:
            filters["type"] = type

        configs_data = await crud_server_mcp_config.get_multi(
            db=db,
            offset=(page - 1) * page_size,
            limit=page_size,
            schema_to_select=ServerMCPConfigRead,
            **filters,
        )

        total = configs_data.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            success=True,
            message="Success",
            data=configs_data["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing MCP configs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{config_id}", response_model=SuccessResponse[ServerMCPConfigRead])
async def get_mcp_config(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config_id: str,
) -> dict[str, Any]:
    """
    Get a specific MCP configuration by ID.

    Returns the `ServerMCPConfigRead` if found and owned by current user.
    """
    try:
        logger.debug(f"Getting MCP config {config_id} for user {current_user['id']}")

        config = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            user_id=current_user["id"],
            is_deleted=False,
            schema_to_select=ServerMCPConfigRead,
        )

        if not config:
            raise NotFoundException("MCP config not found")

        return SuccessResponse(data=config)

    except NotFoundException:
        raise HTTPException(status_code=404, detail="MCP config not found")
    except Exception as e:
        logger.error(f"Error getting MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{config_id}", response_model=SuccessResponse[ServerMCPConfigRead])
async def update_mcp_config(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config_id: str,
    config_update: ServerMCPConfigUpdate,
) -> dict[str, Any]:
    """
    Update an MCP configuration.

    Returns the updated `ServerMCPConfigRead`.
    """
    try:
        logger.debug(f"Updating MCP config {config_id} for user {current_user['id']}")

        # Check ownership
        existing = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            user_id=current_user["id"],
            is_deleted=False,
        )

        if not existing:
            raise NotFoundException("MCP config not found")

        # Prepare update data
        from datetime import datetime, timezone

        update_data = config_update.model_dump(exclude_unset=True)

        # Update tools_last_synced_at if tools are being updated
        if "tools" in update_data and update_data["tools"] is not None:
            update_data["tools_last_synced_at"] = datetime.now(timezone.utc)

        # Update config
        updated = await crud_server_mcp_config.update(
            db=db,
            object=update_data,
            schema_to_select=ServerMCPConfigRead,
        )

        return SuccessResponse(data=updated)

    except NotFoundException:
        raise HTTPException(status_code=404, detail="MCP config not found")
    except ValueError as e:
        logger.warning(f"Validation error updating MCP config: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{config_id}", status_code=204)
async def delete_mcp_config(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config_id: str,
) -> None:
    """
    Delete (soft delete) an MCP configuration.

    Returns 204 No Content on success.
    """
    try:
        logger.debug(f"Deleting MCP config {config_id} for user {current_user['id']}")

        # Check ownership
        existing = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            user_id=current_user["id"],
            is_deleted=False,
        )

        if not existing:
            raise NotFoundException("MCP config not found")

        # Soft delete
        await crud_server_mcp_config.update(
            db=db,
            object={"is_deleted": True},
            id=config_id,
        )

    except NotFoundException:
        raise HTTPException(status_code=404, detail="MCP config not found")
    except Exception as e:
        logger.error(f"Error deleting MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{config_id}/test", response_model=ServerMCPConfigTestResponse)
async def test_mcp_config(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config_id: str,
) -> dict[str, Any]:
    """
    Test MCP configuration connection and get available tools.

    Attempts to connect to the MCP server and retrieve its tools.
    Returns test result with tools or error message.
    """
    try:
        logger.debug(f"Testing MCP config {config_id} for user {current_user['id']}")

        # Get config
        config = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            user_id=current_user["id"],
            is_deleted=False,
            schema_to_select=ServerMCPConfigRead,
            return_as_model=True,
        )

        if not config:
            raise NotFoundException("MCP config not found")

        # Convert to schema if needed
        if isinstance(config, dict):
            config = ServerMCPConfigRead(**config)

        # Test connection - returns dict
        result = await MCPConfigTester.test_config(config)

        # Return test result directly (no SuccessResponse wrapper)
        return result

    except NotFoundException:
        raise HTTPException(status_code=404, detail="MCP config not found")
    except Exception as e:
        logger.error(f"Error testing MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{config_id}/refresh-tools", response_model=ServerMCPConfigRefreshResponse
)
async def refresh_mcp_config_tools(
    request: Request,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    config_id: str,
) -> dict[str, Any]:
    """
    Refresh tools list from MCP server and update database.

    Connects to the MCP server, retrieves current tools, compares with stored tools,
    and updates the database. Returns changelog of added/removed/updated tools.
    """
    try:
        from datetime import datetime, timezone

        logger.debug(
            f"Refreshing tools for MCP config {config_id} for user {current_user['id']}"
        )

        # Get config
        config = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            user_id=current_user["id"],
            is_deleted=False,
            schema_to_select=ServerMCPConfigRead,
            return_as_model=True,
        )

        if not config:
            raise NotFoundException("MCP config not found")

        # Convert to schema if needed
        if isinstance(config, dict):
            config = ServerMCPConfigRead(**config)

        # Store old tools for comparison
        old_tools = None
        if config.tools:
            # Convert MCPToolInfo objects to dicts if needed
            if isinstance(config.tools, list) and len(config.tools) > 0:
                if hasattr(config.tools[0], "model_dump"):
                    old_tools = [tool.model_dump() for tool in config.tools]
                else:
                    old_tools = config.tools

        # Test connection and get new tools
        test_result = await MCPConfigTester.test_config(config)

        if not test_result["success"]:
            # Connection failed - return error but preserve old data
            return {
                "success": False,
                "message": test_result["message"],
                "error": test_result.get("error"),
            }

        # Get new tools from test result
        new_tools = test_result.get("tools", [])

        # Compare tools
        changes = ToolsComparator.compare_tools_lists(old_tools, new_tools)

        # Update database
        await crud_server_mcp_config.update(
            db=db,
            object={
                "tools": new_tools,
                "tools_last_synced_at": datetime.now(timezone.utc),
            },
            id=config_id,
        )

        # Get updated config for response
        updated_config = await crud_server_mcp_config.get(
            db=db,
            id=config_id,
            schema_to_select=ServerMCPConfigRead,
        )

        return {
            "success": True,
            "message": f"Tools refreshed: {len(changes['added'])} added, {len(changes['removed'])} removed, {len(changes['updated'])} updated",
            "data": {
                "tools": new_tools,
                "tools_last_synced_at": (
                    updated_config["tools_last_synced_at"].isoformat()
                    if updated_config.get("tools_last_synced_at")
                    else None
                ),
                "changes": changes,
            },
            "error": None,
        }

    except NotFoundException:
        raise HTTPException(status_code=404, detail="MCP config not found")
    except Exception as e:
        logger.error(f"Error refreshing MCP config tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
