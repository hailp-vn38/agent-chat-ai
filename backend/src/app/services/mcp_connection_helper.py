"""
Integration helper to load user MCP configs in ConnectionHandler.

This module provides utilities for loading user-scoped MCP configurations
and integrating them with the existing ServerMCPManager.
"""

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.logger import get_logger

logger = get_logger(__name__)


async def load_user_mcp_configs(
    user_id: Optional[str],
    db: Optional[AsyncSession],
) -> Optional[List[Dict[str, Any]]]:
    """
    Load MCP configurations for a specific user from the database.

    Args:
        user_id: User ID to load configs for
        db: Database session

    Returns:
        List of MCP config dicts or None if no configs found
    """
    if not user_id or not db:
        return None

    try:
        from ...crud.crud_server_mcp_config import crud_server_mcp_config
        from ...schemas.server_mcp_config import ServerMCPConfigRead

        configs_data = await crud_server_mcp_config.get_multi(
            db=db,
            user_id=user_id,
            is_active=True,
            is_deleted=False,
            schema_to_select=ServerMCPConfigRead,
        )

        if not configs_data or not configs_data.get("data"):
            return None

        # Convert database configs to ServerMCPManager format
        converted_configs = {}
        for config in configs_data["data"]:
            config_dict = (
                config.model_dump() if hasattr(config, "model_dump") else config
            )

            # Convert to mcp_server_settings.json format
            mcp_config = {
                "type": config_dict.get("type"),
            }

            if config_dict.get("type") == "stdio":
                if config_dict.get("command"):
                    mcp_config["command"] = config_dict["command"]
                if config_dict.get("args"):
                    mcp_config["args"] = config_dict["args"]
                if config_dict.get("env"):
                    mcp_config["env"] = config_dict["env"]

            elif config_dict.get("type") in ("sse", "http"):
                if config_dict.get("url"):
                    mcp_config["url"] = config_dict["url"]
                if config_dict.get("headers"):
                    mcp_config["headers"] = config_dict["headers"]

            converted_configs[config_dict["name"]] = mcp_config

        return converted_configs if converted_configs else None

    except Exception as e:
        logger.error(f"Error loading user MCP configs for {user_id}: {str(e)}")
        return None


def filter_tools_by_agent_selection(
    all_tools: List[Dict[str, Any]],
    agent_selection: Optional[Dict[str, Any]],
    mcp_server_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filter tools based on agent's tool selection configuration.

    Args:
        all_tools: All available tools
        agent_selection: Agent's selected_tools configuration (mode + tools array)
        mcp_server_names: List of available MCP server names

    Returns:
        Filtered list of tools based on agent selection
    """
    if not agent_selection:
        # No selection config means use all tools
        return all_tools

    mode = agent_selection.get("mode", "all")
    if mode == "all":
        # Use all tools
        return all_tools

    # Mode is "selected" - filter by specific tools
    selected_tools = agent_selection.get("tools", [])
    if not selected_tools:
        return []

    filtered = []

    for tool in all_tools:
        tool_name = (
            (tool.get("function") or {}).get("name") if isinstance(tool, dict) else ""
        )
        if not tool_name:
            continue

        # Check if this tool should be included
        for tool_ref in selected_tools:
            tool_type = tool_ref.get("type")
            ref_name = tool_ref.get("name")

            # Match MCP tools
            if tool_type == "server_mcp":
                # Wildcard matches all MCP tools
                if ref_name == "*":
                    filtered.append(tool)
                    break
                # Check if tool is from selected MCP server
                # Tool name format might be "server_name:tool_name"
                if ":" in tool_name and tool_name.startswith(ref_name + ":"):
                    filtered.append(tool)
                    break
                elif tool_name == ref_name:
                    filtered.append(tool)
                    break

            # Match server plugins (typically don't use : prefix)
            elif tool_type == "server_plugin" and tool_name == ref_name:
                filtered.append(tool)
                break

    return filtered
