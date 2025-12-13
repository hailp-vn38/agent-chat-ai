"""Tools API router.

Exposes endpoints to:
- Get available tools with schemas for UI rendering
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.schemas.base import PaginatedResponse, SuccessResponse

from ...api.dependencies import get_current_user
from ...core.logger import get_logger
from ...ai.providers.tools.tool_schema_registry import (
    get_tool_schema,
    get_all_tool_schemas,
    get_all_categories,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


# ========== API Endpoints ==========


@router.get("/available")
async def get_available_tools(
    current_user: Annotated[dict, Depends(get_current_user)],
    q: Annotated[
        str | None, Query(description="Search query for function name or description")
    ] = None,
) -> dict[str, Any]:
    """
    Get all available system functions with metadata.

    Returns list of functions from the system registry that can be used in agents.
    Supports optional filtering by name or description via `q` parameter.

    **Response Format (Simplified):**
    - name: Unique function identifier
    - display_name: Human-readable function name
    - description: What the function does
    - category: Function category
    - source_type: Type of tool source (server_plugin, server_mcp, device_mcp)
    - parameters: JSON schema for function parameters

    **Breaking Change:** This endpoint no longer includes schema validation details.
    Custom tool configurations are no longer supported.
    """
    from ...ai.plugins_func.register import all_function_registry

    all_schemas = get_all_tool_schemas()
    tools = []

    for name, schema in all_schemas.items():
        # Skip if query filter doesn't match
        if q:
            q_lower = q.lower()
            if not (
                name.lower().find(q_lower) != -1
                or schema.display_name.lower().find(q_lower) != -1
                or schema.description.lower().find(q_lower) != -1
            ):
                continue

        tool_entry = {
            "name": schema.name,
            "display_name": schema.display_name,
            "description": schema.description,
            "category": schema.category.value,
            "source_type": "server_plugin",  # Default source type
            "parameters": schema.function_schema or {},
        }
        tools.append(tool_entry)

    # Sort by name for consistency
    tools.sort(key=lambda x: x["name"])

    return {
        "success": True,
        "data": tools,
        "total": len(tools),
    }


@router.get("/options")
async def get_tool_options(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get tool options for MULTISELECT dropdown in Intent Provider config.

    Returns system tools available in the registry.

    **Note:** User-defined tool configurations are no longer supported.
    Only system function names are available for selection.
    """
    # Get system tools from registry
    all_schemas = get_all_tool_schemas()
    options = [
        {
            "value": schema.name,
            "label": schema.display_name,
            "description": schema.description,
            "category": schema.category.value,
            "source_type": "server_plugin",  # Add source type
        }
        for schema in all_schemas.values()
    ]

    # Sort by label
    options.sort(key=lambda x: x["label"])

    return {
        "success": True,
        "data": options,
        "total": len(options),
    }


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.get("/schemas/{tool_name}", response_model=ToolSchemaResponse | None)
# async def get_tool_schema_endpoint(tool_name: str) -> ToolSchemaResponse | None:
#     """
#     Get schema for a specific tool.
#
#     Returns None if tool is not found in registry.
#     """
#     schema = get_tool_schema(tool_name)
#     if not schema:
#         raise NotFoundException(f"Tool schema for '{tool_name}' not found")
#
#     fields = [
#         ToolFieldSchemaResponse(
#             name=f.name,
#             display_name=f.display_name,
#             field_type=f.field_type.value,
#             description=f.description,
#             required=f.required,
#             default=f.default,
#             options=f.options,
#             validation=f.validation,
#         )
#         for f in schema.fields
#     ]
#
#     return ToolSchemaResponse(
#         name=schema.name,
#         display_name=schema.display_name,
#         description=schema.description,
#         category=schema.category.value,
#         requires_config=schema.requires_config,
#         fields=fields,
#         function_schema=schema.function_schema,
#     )


# ========== Validation Endpoints ==========


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.post("/validate-reference", response_model=ToolReferenceValidateResponse)
# async def validate_tool_reference(
#     request: ToolReferenceValidateRequest,
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
# ) -> ToolReferenceValidateResponse:
#     """
#     Validate a tool reference.
#
#     Reference can be:
#     - A UUID (UserTool ID)
#     - A tool name from registry (system tool)
#
#     Returns validation result with resolved info.
#     """
#     from ...ai.plugins_func.register import all_function_registry
#
#     reference = request.reference
#     user_id = current_user["id"]
#     errors: list[str] = []
#
#     # Check if it's a UUID (UserTool)
#     # Simple UUID check: contains dashes and is 36 chars
#     is_uuid = len(reference) == 36 and reference.count("-") == 4
#
#     if is_uuid:
#         # Try to find UserTool
#         try:
#             tool = await crud_user_tool.get(
#                 db=db,
#                 id=reference,
#                 user_id=user_id,
#                 is_deleted=False,
#                 schema_to_select=UserToolRead,
#                 return_as_model=True,
#             )
#             if tool:
#                 schema = get_tool_schema(tool.tool_name)
#                 return ToolReferenceValidateResponse(
#                     valid=True,
#                     reference=reference,
#                     source="user",
#                     tool_name=tool.tool_name,
#                     display_name=schema.display_name if schema else tool.name,
#                     errors=[],
#                 )
#             else:
#                 errors.append(
#                     f"UserTool '{reference}' not found or does not belong to user"
#                 )
#         except Exception as e:
#             errors.append(f"Failed to query UserTool: {str(e)}")
#     else:
#         # Check if it's a system tool name
#         if reference in all_function_registry:
#             schema = get_tool_schema(reference)
#             return ToolReferenceValidateResponse(
#                 valid=True,
#                 reference=reference,
#                 source="system",
#                 tool_name=reference,
#                 display_name=schema.display_name if schema else reference,
#                 errors=[],
#             )
#         else:
#             errors.append(f"Tool '{reference}' not found in registry")
#
#     return ToolReferenceValidateResponse(
#         valid=False,
#         reference=reference,
#         source=None,
#         tool_name=None,
#         display_name=None,
#         errors=errors,
#     )


# ========== CRUD Endpoints ==========


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.get("", response_model=PaginatedResponse[UserToolRead])
# async def list_user_tools(
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
#     tool_name: Annotated[str | None, Query(description="Filter by tool name")] = None,
#     page: Annotated[int, Query(ge=1)] = 1,
#     page_size: Annotated[int, Query(ge=1, le=100)] = 10,
# ) -> dict[str, Any]:
#     """
#     List user's tool configurations with pagination.
#
#     Optionally filter by tool_name to get all configs for a specific tool.
#     """
#     user_id = current_user["id"]
#     offset = (page - 1) * page_size
#
#     # Build filters
#     filters: dict[str, Any] = {
#         "user_id": user_id,
#         "is_deleted": False,
#     }
#     if tool_name:
#         filters["tool_name"] = tool_name
#
#     result = await crud_user_tool.get_multi(
#         db=db,
#         offset=offset,
#         limit=page_size,
#         schema_to_select=UserToolRead,
#         return_as_model=True,
#         **filters,
#     )
#
#     tools = result.get("data", [])
#     total = result.get("total_count", 0)
#     total_pages = (total + page_size - 1) // page_size if total > 0 else 0
#
#     # Mask secrets
#     data = []
#     for tool in tools:
#         tool_dict = tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)
#         tool_dict["config"] = mask_secrets(tool_dict["config"], tool_dict["tool_name"])
#         data.append(tool_dict)
#
#     return {
#         "success": True,
#         "message": "Success",
#         "data": data,
#         "total": total,
#         "page": page,
#         "page_size": page_size,
#         "total_pages": total_pages,
#     }


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.post("", response_model=SuccessResponse[UserToolRead], status_code=201)
# async def create_user_tool(
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
#     tool: UserToolCreate,
# ) -> dict[str, Any]:
#     """
#     Create a new tool configuration.
#
#     Tool name must exist in the tool registry.
#     Config is validated against the tool's schema.
#     """
#     from ...ai.plugins_func.register import all_function_registry
#
#     user_id = current_user["id"]
#
#     # Validate tool_name exists in registry
#     if tool.tool_name not in all_function_registry:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Tool '{tool.tool_name}' not found in registry",
#         )
#
#     # Validate config
#     is_valid, normalized, errors = validate_tool_config(tool.tool_name, tool.config)
#     if not is_valid:
#         raise HTTPException(status_code=400, detail={"errors": errors})
#
#     # Create tool config
#     tool_internal = UserToolCreateInternal(
#         user_id=user_id,
#         tool_name=tool.tool_name,
#         name=tool.name,
#         config=normalized,
#         is_active=tool.is_active,
#     )
#
#     created = await crud_user_tool.create(db=db, object=tool_internal)
#
#     # Convert to response
#     created_dict = {
#         "id": created.id,
#         "user_id": created.user_id,
#         "tool_name": created.tool_name,
#         "name": created.name,
#         "config": mask_secrets(created.config, created.tool_name),
#         "is_active": created.is_active,
#         "created_at": created.created_at,
#         "updated_at": created.updated_at,
#         "is_deleted": created.is_deleted,
#     }
#
#     return {
#         "success": True,
#         "message": "Tool configuration created successfully",
#         "data": created_dict,
#     }


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.get("/{tool_id}", response_model=SuccessResponse[UserToolRead])
# async def get_user_tool(
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
#     tool_id: str,
# ) -> dict[str, Any]:
#     """
#     Get a specific tool configuration by ID.
#
#     Only returns tool if it belongs to the current user.
#     """
#     user_id = current_user["id"]
#     tool = await verify_tool_ownership(db, tool_id, user_id)
#
#     tool_dict = tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)
#     tool_dict["config"] = mask_secrets(tool_dict["config"], tool_dict["tool_name"])
#
#     return {
#         "success": True,
#         "message": "Success",
#         "data": tool_dict,
#     }


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.put("/{tool_id}", response_model=SuccessResponse[UserToolRead])
# async def update_user_tool(
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
#     tool_id: str,
#     update_data: UserToolUpdate,
# ) -> dict[str, Any]:
#     """
#     Update a tool configuration.
#
#     If config is provided, it's validated against the tool's schema.
#     """
#     user_id = current_user["id"]
#     existing = await verify_tool_ownership(db, tool_id, user_id)
#
#     existing_dict = (
#         existing.model_dump() if hasattr(existing, "model_dump") else dict(existing)
#     )
#
#     # Validate config if provided
#     if update_data.config is not None:
#         is_valid, normalized, errors = validate_tool_config(
#             existing_dict["tool_name"], update_data.config
#         )
#         if not is_valid:
#             raise HTTPException(status_code=400, detail={"errors": errors})
#         update_data.config = normalized
#
#     # Build update dict
#     update_dict: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
#     if update_data.name is not None:
#         update_dict["name"] = update_data.name
#     if update_data.config is not None:
#         update_dict["config"] = update_data.config
#     if update_data.is_active is not None:
#         update_dict["is_active"] = update_data.is_active
#
#     await crud_user_tool.update(
#         db=db,
#         object=update_dict,
#         id=tool_id,
#         user_id=user_id,
#     )
#
#     # Get updated tool
#     updated = await verify_tool_ownership(db, tool_id, user_id)
#     result = updated.model_dump() if hasattr(updated, "model_dump") else dict(updated)
#     result["config"] = mask_secrets(result["config"], result["tool_name"])
#
#     return {
#         "success": True,
#         "message": "Tool configuration updated successfully",
#         "data": result,
#     }


# DEPRECATED: Endpoint disabled as part of tool management simplification
# @router.delete("/{tool_id}", status_code=204)
# async def delete_user_tool(
#     db: Annotated[AsyncSession, Depends(async_get_db)],
#     current_user: Annotated[dict, Depends(get_current_user)],
#     tool_id: str,
# ) -> None:
#     """
#     Delete a tool configuration (soft delete).
#     """
#     user_id = current_user["id"]
#     await verify_tool_ownership(db, tool_id, user_id)
#
#     await crud_user_tool.delete(db=db, id=tool_id)
