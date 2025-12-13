"""
MCP Metadata Resolver service - resolves MCP references to complete metadata.

Supports:
- User-defined MCPs: db:{uuid} → lookup in server_mcp_config
- System MCPs: config:{name} → lookup in config.yml
"""

from typing import Any
import re

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..crud.crud_server_mcp_config import crud_server_mcp_config
from .config_mcp_loader import ConfigMCPLoader

logger = get_logger(__name__)

# Reference format validation
REFERENCE_PATTERN = r"^(db:[a-f0-9\-]{36}|config:[a-zA-Z0-9_\-]+)$"
DB_REFERENCE_PATTERN = r"^db:([a-f0-9\-]{36})$"
CONFIG_REFERENCE_PATTERN = r"^config:([a-zA-Z0-9_\-]+)$"


class MCPMetadataResolver:
    """Resolves MCP references to complete metadata."""

    @staticmethod
    async def resolve_from_db(
        reference: str, user_id: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Resolve user-defined MCP reference (db:uuid) to metadata.

        Args:
            reference: Reference in format 'db:{uuid}'
            user_id: User ID for ownership validation
            db: AsyncSession

        Returns:
            dict with keys: reference, mcp_name, mcp_type, mcp_description, source, is_active

        Raises:
            ValueError: If reference format invalid, MCP not found, or user doesn't own it
        """
        match = re.match(DB_REFERENCE_PATTERN, reference)
        if not match:
            raise ValueError(f"Invalid db reference format: {reference}")

        mcp_id = match.group(1)

        try:
            # Query server_mcp_config
            from ..schemas.server_mcp_config import ServerMCPConfigRead

            mcp_config = await crud_server_mcp_config.get(
                db=db,
                id=mcp_id,
                user_id=user_id,  # Ownership check
                is_deleted=False,
                schema_to_select=ServerMCPConfigRead,
                return_as_model=True,
            )

            if not mcp_config:
                raise ValueError(
                    f"MCP server {mcp_id} not found or you don't have permission to access it"
                )

            return {
                "reference": reference,
                "mcp_name": mcp_config.name,
                "mcp_type": mcp_config.type,
                "mcp_description": mcp_config.description,
                "source": "user",
                "is_active": mcp_config.is_active,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error resolving db reference {reference}: {e}")
            raise ValueError(f"Failed to resolve db reference {reference}: {str(e)}")

    @staticmethod
    async def resolve_from_config(reference: str) -> dict[str, Any]:
        """
        Resolve system MCP reference (config:name) to metadata from JSON config file.

        Args:
            reference: Reference in format 'config:{name}'

        Returns:
            dict with keys: reference, mcp_name, mcp_type, mcp_description, source

        Raises:
            ValueError: If reference format invalid or config MCP not found
        """
        match = re.match(CONFIG_REFERENCE_PATTERN, reference)
        if not match:
            raise ValueError(f"Invalid config reference format: {reference}")

        mcp_name = match.group(1)

        try:
            # Load MCPs from config JSON file
            config_mcp = ConfigMCPLoader.get_server(mcp_name)

            if not config_mcp:
                available = ConfigMCPLoader.get_server_names()
                raise ValueError(
                    f"Config MCP '{mcp_name}' not found. Available: {available}"
                )

            return {
                "reference": reference,
                "mcp_name": mcp_name,
                "mcp_type": config_mcp.get("type", "stdio"),
                "mcp_description": config_mcp.get("description", ""),
                "source": "config",
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error resolving config reference {reference}: {e}")
            raise ValueError(
                f"Failed to resolve config reference {reference}: {str(e)}"
            )

    @staticmethod
    async def resolve_all(
        references: list[str], user_id: str, db: AsyncSession
    ) -> list[dict[str, Any]]:
        """
        Resolve list of mixed MCP references (both db: and config:) to metadata.

        Args:
            references: List of references in formats 'db:{uuid}' or 'config:{name}'
            user_id: User ID for ownership validation of db references
            db: AsyncSession

        Returns:
            List of resolved metadata dicts in same order as input
            Each dict has keys: reference, mcp_name, mcp_type, mcp_description, source, is_active

        Raises:
            ValueError: If any reference invalid or resolution fails
        """
        if not references:
            return []

        logger.debug(f"Resolving {len(references)} MCP references")

        # Separate db and config references
        db_refs = []
        config_refs = []
        ref_indices = {}  # Map reference to original index

        for idx, ref in enumerate(references):
            if ref.startswith("db:"):
                db_refs.append(ref)
                ref_indices[ref] = idx
            elif ref.startswith("config:"):
                config_refs.append(ref)
                ref_indices[ref] = idx
            else:
                raise ValueError(f"Invalid reference format: {ref}")

        resolved = [None] * len(references)
        errors = []

        # Resolve db references (batch)
        if db_refs:
            try:
                from ..schemas.server_mcp_config import ServerMCPConfigRead

                # Extract UUIDs
                db_ids = [ref.split(":")[1] for ref in db_refs]

                # Batch query
                result = await crud_server_mcp_config.get_multi(
                    db=db,
                    id__in=db_ids,
                    user_id=user_id,
                    is_deleted=False,
                    schema_to_select=ServerMCPConfigRead,
                    return_as_model=True,
                )

                mcp_map = {mcp.id: mcp for mcp in result.get("data", [])}

                for ref in db_refs:
                    mcp_id = ref.split(":")[1]
                    if mcp_id not in mcp_map:
                        errors.append(f"{ref} - not found or permission denied")
                        continue

                    mcp = mcp_map[mcp_id]
                    resolved[ref_indices[ref]] = {
                        "reference": ref,
                        "mcp_name": mcp.name,
                        "mcp_type": mcp.type,
                        "mcp_description": mcp.description,
                        "source": "user",
                        "is_active": mcp.is_active,
                    }

            except Exception as e:
                logger.error(f"Error batch resolving db references: {e}")
                for ref in db_refs:
                    errors.append(f"{ref} - resolution error: {str(e)}")

        # Resolve config references
        for ref in config_refs:
            try:
                metadata = await MCPMetadataResolver.resolve_from_config(ref)
                resolved[ref_indices[ref]] = metadata
            except ValueError as e:
                errors.append(f"{ref} - {str(e)}")

        # Check for any failures
        if errors:
            error_msg = "Failed to resolve MCP references: " + "; ".join(errors)
            logger.warning(error_msg)
            raise ValueError(error_msg)

        # Verify all resolved
        if None in resolved:
            raise ValueError("Internal error: some references not resolved")

        logger.debug(f"Successfully resolved {len(resolved)} MCP references")
        return resolved
