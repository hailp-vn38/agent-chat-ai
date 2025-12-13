"""
ToolConfigResolver - Simplified utility to resolve tool references.

Now only handles system tool names (no UserTool support).
"""

from typing import Any

from app.ai.plugins_func.register import all_function_registry
from app.core.logger import get_logger

logger = get_logger(__name__)


class ToolConfigResolver:
    """Resolve tool references to tool names."""

    def __init__(self, base_config: dict):
        """
        Initialize resolver.

        Args:
            base_config: Base config (from config.yml) for plugin configs
        """
        self.base_config = base_config

    def resolve_tools(
        self,
        tool_refs: list[str],
    ) -> list[dict[str, Any]]:
        """
        Resolve list of tool names to tool configs.

        Args:
            tool_refs: List of system tool function names

        Returns:
            List of resolved tools with format:
            [
                {
                    "name": "get_weather",
                    "config": {...},
                },
                ...
            ]
        """
        resolved = []

        for ref in tool_refs:
            tool_info = self._resolve_system_tool(ref)
            if tool_info:
                resolved.append(tool_info)
            else:
                logger.warning(f"Could not resolve tool reference: {ref}")

        return resolved

    def _resolve_system_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Resolve system tool by name."""
        if tool_name not in all_function_registry:
            logger.warning(f"Tool '{tool_name}' not found in registry")
            return None

        # Get config from config["plugins"] if exists
        config = self._get_base_tool_config(tool_name)

        return {
            "name": tool_name,
            "config": config,
        }

    def _get_base_tool_config(self, tool_name: str) -> dict[str, Any]:
        """Get tool config from config["plugins"]."""
        plugins = self.base_config.get("plugins", {})
        return plugins.get(tool_name, {})


def get_tool_names_from_refs(
    tool_refs: list[str] | None,
    fallback_functions: list[str] | None = None,
) -> list[str]:
    """
    Extract tool names from references (simple sync version).

    Args:
        tool_refs: List of tool function names from agent config
        fallback_functions: Fallback functions from config["Intent"]["functions"]

    Returns:
        List of tool names
    """
    if not tool_refs:
        return fallback_functions or []

    return tool_refs
