"""
MCP reference validator service.

Validates references to MCP servers (user-defined or config-based) in agent configuration.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .config_mcp_loader import ConfigMCPLoader


class MCPReferenceValidator:
    """Validator for MCP server references in agent configuration."""

    @staticmethod
    def parse_reference(reference: str) -> tuple[str, str]:
        """Parse MCP reference into source and identifier.

        Args:
            reference: MCP reference (db:uuid or config:name)

        Returns:
            Tuple of (source, identifier)

        Raises:
            ValueError: If reference format is invalid
        """
        if not reference or ":" not in reference:
            raise ValueError(f"Invalid MCP reference format: '{reference}'")

        parts = reference.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid MCP reference format: '{reference}'")

        source, identifier = parts

        if source not in ("db", "config"):
            raise ValueError(
                f"Invalid MCP reference source: '{source}'. Must be 'db' or 'config'"
            )

        if not identifier:
            raise ValueError(f"Empty identifier in MCP reference: '{reference}'")

        return source, identifier

    @staticmethod
    async def validate_user_mcp_exists(
        db: AsyncSession,
        mcp_id: str,
        user_id: str,
    ) -> bool:
        """Check if user MCP server exists.

        Args:
            db: Database session
            mcp_id: MCP server UUID
            user_id: User ID

        Returns:
            True if exists

        Raises:
            ValueError: If MCP server not found
        """
        from ..crud.crud_server_mcp_config import crud_server_mcp_config

        config = await crud_server_mcp_config.get(
            db=db,
            id=mcp_id,
            user_id=user_id,
            is_deleted=False,
            is_active=True,
        )

        if not config:
            raise ValueError(f"User MCP server '{mcp_id}' not found or inactive")

        return True

    @staticmethod
    def validate_config_mcp_exists(mcp_name: str) -> bool:
        """Check if config MCP server exists.

        Args:
            mcp_name: MCP server name from config

        Returns:
            True if exists

        Raises:
            ValueError: If MCP server not found in config
        """
        if not ConfigMCPLoader.exists(mcp_name):
            available = ", ".join(sorted(ConfigMCPLoader.get_server_names()))
            raise ValueError(
                f"Config MCP server '{mcp_name}' not found. Available: {available}"
            )

        return True

    @staticmethod
    async def validate_mcp_reference(
        reference: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Validate a complete MCP server reference.

        Args:
            reference: MCP reference (db:uuid or config:name)
            user_id: User ID
            db: Database session (required for user MCP validation)

        Raises:
            ValueError: If validation fails
        """
        source, identifier = MCPReferenceValidator.parse_reference(reference)

        if source == "db":
            if not db:
                raise ValueError("Database session required for user MCP validation")
            await MCPReferenceValidator.validate_user_mcp_exists(
                db, identifier, user_id
            )

        elif source == "config":
            MCPReferenceValidator.validate_config_mcp_exists(identifier)

    @staticmethod
    async def validate_all_mcp_references(
        references: list[str],
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Validate multiple MCP server references.

        Args:
            references: List of MCP references (db:uuid or config:name)
            user_id: User ID
            db: Database session

        Raises:
            ValueError: If any reference is invalid
        """
        if not isinstance(references, list):
            raise ValueError("MCP references must be a list")

        if not references:
            raise ValueError("At least one MCP server reference is required")

        if len(references) > 50:
            raise ValueError("Too many MCP references (max 50)")

        for idx, reference in enumerate(references):
            if not isinstance(reference, str):
                raise ValueError(f"MCP reference {idx} must be a string")

            try:
                await MCPReferenceValidator.validate_mcp_reference(
                    reference,
                    user_id,
                    db,
                )
            except ValueError as e:
                raise ValueError(f"MCP reference {idx} ('{reference}'): {str(e)}")
