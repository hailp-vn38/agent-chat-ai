"""
Server plugin management endpoints.

Exposes APIs to list, test, and validate server plugins (custom server functions).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import asyncio

from ...api.dependencies import get_current_user
from ...core.logger import get_logger
from ...schemas.base import SuccessResponse
from ...ai.providers.tools.tool_schema_registry import (
    get_all_tool_schemas,
    get_all_categories,
)
from ...ai.plugins_func.register import all_function_registry

router = APIRouter(tags=["plugins"], prefix="/tools/plugins")

logger = get_logger(__name__)


@router.get("", response_model=SuccessResponse[dict])
async def list_plugins(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    category: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """
    List all available server plugins.

    Returns list of plugins with metadata.
    Can be filtered by category or search query.
    """
    try:
        logger.debug(f"Listing plugins for user {current_user['id']}")

        all_schemas = get_all_tool_schemas()
        plugins = []

        for name, schema in all_schemas.items():
            # Filter by category if specified
            if category and str(schema.category.value) != category:
                continue

            # Filter by search if specified
            if search:
                search_lower = search.lower()
                if not (
                    name.lower().find(search_lower) != -1
                    or schema.display_name.lower().find(search_lower) != -1
                    or schema.description.lower().find(search_lower) != -1
                ):
                    continue

            plugin_entry = {
                "name": name,
                "display_name": schema.display_name,
                "description": schema.description,
                "category": schema.category.value,
                "parameters": schema.function_schema or {},
            }
            plugins.append(plugin_entry)

        # Sort by name
        plugins.sort(key=lambda x: x["name"])

        return SuccessResponse(
            data={
                "plugins": plugins,
                "total": len(plugins),
                "category_filter": category,
                "search_filter": search,
            }
        )

    except Exception as e:
        logger.error(f"Error listing plugins: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{plugin_name}", response_model=SuccessResponse[dict])
async def get_plugin_detail(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    plugin_name: str,
) -> dict[str, Any]:
    """
    Get detailed information about a specific server plugin.

    Returns the plugin schema and metadata.
    """
    try:
        logger.debug(f"Getting plugin detail for {plugin_name}")

        all_schemas = get_all_tool_schemas()

        if plugin_name not in all_schemas:
            raise HTTPException(status_code=404, detail="Plugin not found")

        schema = all_schemas[plugin_name]

        return SuccessResponse(
            data={
                "name": plugin_name,
                "display_name": schema.display_name,
                "description": schema.description,
                "category": schema.category.value,
                "parameters": schema.function_schema or {},
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plugin detail: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{plugin_name}/test", response_model=SuccessResponse[dict])
async def test_plugin(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    plugin_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Test a server plugin by executing it with provided arguments.

    Executes the plugin function with given arguments and returns the result.
    Errors are caught and returned safely.
    """
    try:
        logger.debug(f"Testing plugin {plugin_name} for user {current_user['id']}")

        # Check plugin exists
        if plugin_name not in all_function_registry:
            raise HTTPException(status_code=404, detail="Plugin not found")

        # Get plugin function
        plugin_func = all_function_registry[plugin_name]

        if not args:
            args = {}

        # Execute plugin with timeout
        try:
            result = await asyncio.wait_for(
                plugin_func(**args),
                timeout=10,
            )

            return SuccessResponse(
                data={
                    "success": True,
                    "plugin": plugin_name,
                    "result": result,
                }
            )

        except asyncio.TimeoutError:
            return SuccessResponse(
                data={
                    "success": False,
                    "plugin": plugin_name,
                    "error": "Plugin execution timeout",
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing plugin: {str(e)}")
        return SuccessResponse(
            data={
                "success": False,
                "plugin": plugin_name,
                "error": str(e),
            }
        )


@router.post("/{plugin_name}/validate", response_model=SuccessResponse[dict])
async def validate_plugin_args(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    plugin_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Validate arguments for a server plugin without executing it.

    Returns validation result with any errors found.
    """
    try:
        logger.debug(f"Validating plugin {plugin_name} arguments")

        all_schemas = get_all_tool_schemas()

        if plugin_name not in all_schemas:
            raise HTTPException(status_code=404, detail="Plugin not found")

        schema = all_schemas[plugin_name]
        function_schema = schema.function_schema or {}

        if not args:
            args = {}

        # Simple validation: check required fields
        required_fields = function_schema.get("required", [])
        missing_fields = [field for field in required_fields if field not in args]

        is_valid = len(missing_fields) == 0

        return SuccessResponse(
            data={
                "valid": is_valid,
                "plugin": plugin_name,
                "missing_fields": missing_fields,
                "provided_fields": list(args.keys()),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating plugin args: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories/list", response_model=SuccessResponse[dict])
async def get_plugin_categories(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get list of available plugin categories with plugin counts.

    Returns unique categories and the number of plugins in each.
    """
    try:
        logger.debug(f"Getting plugin categories for user {current_user['id']}")

        categories = get_all_categories()
        all_schemas = get_all_tool_schemas()

        # Count plugins per category
        category_counts = {}
        for name, schema in all_schemas.items():
            cat = schema.category.value
            if cat not in category_counts:
                category_counts[cat] = 0
            category_counts[cat] += 1

        return SuccessResponse(
            data={
                "categories": [
                    {
                        "name": cat,
                        "count": category_counts.get(cat, 0),
                    }
                    for cat in sorted(category_counts.keys())
                ],
                "total_categories": len(category_counts),
                "total_plugins": len(all_schemas),
            }
        )

    except Exception as e:
        logger.error(f"Error getting plugin categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
