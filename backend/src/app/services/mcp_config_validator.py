"""
MCP configuration validator service.

Validates MCP server configurations for security, format, and feasibility.
"""

import re
from typing import Optional

from ..schemas.server_mcp_config import ServerMCPConfigCreate


class MCPConfigValidator:
    """Validator for MCP server configurations."""

    # Allowed commands for stdio transport
    ALLOWED_COMMANDS = {"npx", "node", "python", "python3","uvx"}

    # Shell metacharacters to avoid in args
    SHELL_METACHARACTERS = {
        ";",
        "|",
        "&",
        ">",
        "<",
        "`",
        "$",
        "!",
        "*",
        "?",
        "'",
        '"',
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
    }

    # Name pattern: snake_case
    NAME_PATTERN = re.compile(r"^[a-z0-9_]{3,255}$")

    @classmethod
    def validate_name(cls, name: str) -> None:
        """Validate config name format.

        Args:
            name: Configuration name

        Raises:
            ValueError: If name format is invalid
        """
        if not cls.NAME_PATTERN.match(name):
            raise ValueError(
                "Name must be 3-255 characters, lowercase, alphanumeric or underscore only"
            )

    @classmethod
    def validate_command(cls, command: str) -> None:
        """Validate stdio command.

        Args:
            command: Command name (e.g., 'npx', 'node')

        Raises:
            ValueError: If command is not in allowlist
        """
        if command not in cls.ALLOWED_COMMANDS:
            allowed = ", ".join(sorted(cls.ALLOWED_COMMANDS))
            raise ValueError(
                f"Command '{command}' not allowed. Allowed commands: {allowed}"
            )

    @classmethod
    def validate_args(cls, args: list[str] | None) -> None:
        """Validate stdio command arguments.

        Args:
            args: List of command arguments

        Raises:
            ValueError: If args contain shell metacharacters or are invalid
        """
        if not args:
            return

        if not isinstance(args, list):
            raise ValueError("Args must be a list of strings")

        for arg in args:
            if not isinstance(arg, str):
                raise ValueError(f"Argument must be string, got {type(arg)}")

            # Check for shell metacharacters
            if any(char in arg for char in cls.SHELL_METACHARACTERS):
                raise ValueError(f"Argument contains forbidden characters: {arg}")

    @classmethod
    def validate_env(cls, env: dict[str, str] | None) -> None:
        """Validate environment variables.

        Args:
            env: Environment variable dictionary

        Raises:
            ValueError: If env format is invalid
        """
        if not env:
            return

        if not isinstance(env, dict):
            raise ValueError("Env must be a dictionary")

        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("Environment variables must be string key-value pairs")

    @classmethod
    def validate_url(cls, url: str) -> None:
        """Validate HTTP/SSE URL.

        Args:
            url: URL string

        Raises:
            ValueError: If URL format is invalid
        """
        if not url:
            return

        if not isinstance(url, str):
            raise ValueError("URL must be a string")

        if len(url) > 2048:
            raise ValueError("URL is too long (max 2048 characters)")

        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")

    @classmethod
    def validate_headers(cls, headers: dict[str, str] | None) -> None:
        """Validate HTTP headers.

        Args:
            headers: Headers dictionary

        Raises:
            ValueError: If headers format is invalid
        """
        if not headers:
            return

        if not isinstance(headers, dict):
            raise ValueError("Headers must be a dictionary")

        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("Headers must be string key-value pairs")

    @classmethod
    def validate_config(cls, config: ServerMCPConfigCreate) -> None:
        """Validate entire MCP config.

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If any validation fails
        """
        # Validate name
        cls.validate_name(config.name)

        # Type-specific validation
        if config.type == "stdio":
            if not config.command:
                raise ValueError("command is required for stdio transport")
            cls.validate_command(config.command)
            cls.validate_args(config.args)
            cls.validate_env(config.env)

        elif config.type in ("sse", "http"):
            if not config.url:
                raise ValueError(f"url is required for {config.type} transport")
            cls.validate_url(config.url)
            cls.validate_headers(config.headers)

        else:
            raise ValueError(f"Unknown transport type: {config.type}")
