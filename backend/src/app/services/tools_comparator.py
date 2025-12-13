"""
Tools comparator service - Compare two lists of MCP tools.

Detects added, removed, and updated tools between two tool lists.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ToolsComparator:
    """Service for comparing MCP tools lists."""

    @staticmethod
    def compare_tools_lists(
        old_tools: list[dict[str, Any]] | None,
        new_tools: list[dict[str, Any]] | None,
    ) -> dict[str, list]:
        """Compare two tools lists and detect changes.

        Args:
            old_tools: Previous tools list (can be None)
            new_tools: New tools list (can be None)

        Returns:
            Dict with:
                - added: Tools in new but not in old
                - removed: Tools in old but not in new
                - updated: Tools with same name but different content
        """
        # Handle None cases
        old_tools = old_tools or []
        new_tools = new_tools or []

        # Build lookup dicts by name
        old_dict = {tool["name"]: tool for tool in old_tools}
        new_dict = {tool["name"]: tool for tool in new_tools}

        # Find added tools
        added = [new_dict[name] for name in new_dict.keys() if name not in old_dict]

        # Find removed tools
        removed = [old_dict[name] for name in old_dict.keys() if name not in new_dict]

        # Find updated tools (same name, different content)
        updated = []
        for name in old_dict.keys():
            if name in new_dict:
                old_tool = old_dict[name]
                new_tool = new_dict[name]

                # Deep compare (description or inputSchema changed)
                if old_tool.get("description") != new_tool.get(
                    "description"
                ) or old_tool.get("inputSchema") != new_tool.get("inputSchema"):
                    updated.append({"old": old_tool, "new": new_tool})

        logger.debug(
            f"Tools comparison: {len(added)} added, {len(removed)} removed, {len(updated)} updated"
        )

        return {
            "added": added,
            "removed": removed,
            "updated": updated,
        }
