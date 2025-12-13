"""
ConfigMCPLoader - Utility to load and cache MCP servers from JSON config file.

Loads MCP server configurations from mcp_server_settings.json and provides
a unified interface for accessing config-based MCP servers.
"""

import json
from pathlib import Path
from typing import Any

from ..core.logger import get_logger

logger = get_logger(__name__)

# Cache for config MCP servers (loaded once)
_config_mcp_cache: dict[str, dict[str, Any]] | None = None


def _get_config_file_path() -> Path:
    """Get path to mcp_server_settings.json file."""
    return Path(__file__).parent.parent / "data" / "mcp_server_settings.json"


def _normalize_transport_type(transport: str | None) -> str:
    """Normalize transport type to standard type values.

    Mapping:
    - streamable-http → http
    - sse → sse
    - stdio → stdio
    - None/empty → stdio (default)
    """
    if not transport:
        return "stdio"

    transport = transport.lower()

    if transport in ("streamable-http", "http"):
        return "http"
    elif transport == "sse":
        return "sse"
    else:
        return "stdio"


class ConfigMCPLoader:
    """Utility class to load and access config-based MCP servers."""

    @staticmethod
    def load_config(force_reload: bool = False) -> dict[str, dict[str, Any]]:
        """
        Load MCP servers from config JSON file.

        Args:
            force_reload: If True, reload from file even if cached

        Returns:
            Dict mapping server name to config dict.
            Each config has: name, type, description, url/command, source="config"
        """
        global _config_mcp_cache

        if _config_mcp_cache is not None and not force_reload:
            return _config_mcp_cache

        config_path = _get_config_file_path()

        if not config_path.exists():
            logger.warning(f"MCP config file not found: {config_path}")
            _config_mcp_cache = {}
            return _config_mcp_cache

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = json.load(f)

            servers = raw_config.get("mcpServers", {})
            normalized: dict[str, dict[str, Any]] = {}

            for name, config in servers.items():
                # Normalize config to standard format
                # Use 'or' pattern to handle explicit None values
                normalized[name] = {
                    "name": name,
                    "type": _normalize_transport_type(config.get("transport")),
                    "description": config.get("des") or config.get("description") or "",
                    "source": "config",
                    "is_active": True,
                    # Preserve original fields for connection
                    "url": config.get("url"),
                    "command": config.get("command"),
                    "args": config.get("args") or [],
                    "env": config.get("env") or {},
                    "headers": config.get("headers") or {},
                    # Original transport for special handling
                    "_transport": config.get("transport"),
                }

            _config_mcp_cache = normalized
            logger.info(
                f"Loaded {len(normalized)} MCP servers from config: {list(normalized.keys())}"
            )
            return _config_mcp_cache

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP config file {config_path}: {e}")
            _config_mcp_cache = {}
            return _config_mcp_cache
        except Exception as e:
            logger.error(f"Error loading MCP config file {config_path}: {e}")
            _config_mcp_cache = {}
            return _config_mcp_cache

    @staticmethod
    def get_server(name: str) -> dict[str, Any] | None:
        """
        Get a specific config MCP server by name.

        Args:
            name: Server name (key in mcpServers)

        Returns:
            Server config dict or None if not found
        """
        servers = ConfigMCPLoader.load_config()
        return servers.get(name)

    @staticmethod
    def get_all_servers() -> list[dict[str, Any]]:
        """
        Get all config MCP servers as a list.

        Returns:
            List of server config dicts
        """
        servers = ConfigMCPLoader.load_config()
        return list(servers.values())

    @staticmethod
    def get_server_names() -> list[str]:
        """
        Get list of all config MCP server names.

        Returns:
            List of server names
        """
        servers = ConfigMCPLoader.load_config()
        return list(servers.keys())

    @staticmethod
    def exists(name: str) -> bool:
        """
        Check if a config MCP server exists.

        Args:
            name: Server name to check

        Returns:
            True if exists, False otherwise
        """
        servers = ConfigMCPLoader.load_config()
        return name in servers

    @staticmethod
    def clear_cache() -> None:
        """Clear the config cache to force reload on next access."""
        global _config_mcp_cache
        _config_mcp_cache = None
        logger.debug("Config MCP cache cleared")
