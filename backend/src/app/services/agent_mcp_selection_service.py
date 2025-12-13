"""
Agent MCP Selection Service - manages agent MCP selection operations.

Handles:
- Get agent MCP selection with resolved metadata
- Update agent MCP selection with validation and resolution
- Supports both 'all' and 'selected' modes
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..core.exceptions.http_exceptions import NotFoundException
from ..schemas.agent import (
    MCPSelection,
    AgentRead,
    AgentMCPSelectionRead,
    AgentMCPServerSelectedRead,
    AgentMCPSelectionCreate,
    AgentMCPServerSelectedCreate,
)
from ..crud.crud_agent import crud_agent
from ..crud.crud_agent_mcp_selection import (
    crud_agent_mcp_selection,
    crud_agent_mcp_server_selected,
)
from ..crud.crud_server_mcp_config import crud_server_mcp_config
from .mcp_metadata_resolver import MCPMetadataResolver
from .mcp_reference_validator import MCPReferenceValidator
from .config_mcp_loader import ConfigMCPLoader

logger = get_logger(__name__)

STALE_THRESHOLD_DAYS = 7


class AgentMCPSelectionService:
    """Service for managing agent MCP selections."""

    @staticmethod
    async def get_selection(
        agent_id: str,
        user_id: str,
        db: AsyncSession,
    ) -> AgentMCPSelectionRead:
        """
        Get agent MCP selection with all resolved metadata.

        Single JOIN query - no additional lookups needed.

        Args:
            agent_id: Agent ID
            user_id: User ID (for ownership validation)
            db: AsyncSession

        Returns:
            AgentMCPSelectionRead with all servers and metadata

        Raises:
            NotFoundException: If agent not found or user doesn't own it
        """
        try:
            logger.debug(f"Getting MCP selection for agent {agent_id}, user {user_id}")

            # Verify agent exists and user owns it
            agent = await crud_agent.get(
                db=db,
                id=agent_id,
                user_id=user_id,
                is_deleted=False,
                schema_to_select=AgentRead,
                return_as_model=True,
            )

            if not agent:
                raise NotFoundException("Agent not found")

            # Get selection with servers (single join query)
            selection = await crud_agent_mcp_selection.get_joined(
                db=db,
                agent_id=agent_id,
            )

            if not selection:
                # Create default selection if doesn't exist
                logger.debug(
                    f"No MCP selection found for agent {agent_id}, creating default"
                )
                selection_data = await crud_agent_mcp_selection.create(
                    db=db,
                    object=AgentMCPSelectionCreate(
                        agent_id=agent_id,
                        mcp_selection_mode="all",
                    ),
                )
                return AgentMCPSelectionRead(
                    id=selection_data.id,
                    agent_id=agent_id,
                    mcp_selection_mode="all",
                    servers=[],
                    created_at=selection_data.created_at,
                    updated_at=selection_data.updated_at,
                )

            # Build response with staleness check
            servers = []
            if selection.mcp_selection_mode == "all":
                # Fetch ALL active MCP configs for this user
                all_configs = await crud_server_mcp_config.get_multi(
                    db=db,
                    user_id=agent.user_id,
                    is_active=True,
                    is_deleted=False,
                )

                for cfg in all_configs.get("data", []):
                    cfg_dict = (
                        cfg.model_dump() if hasattr(cfg, "model_dump") else dict(cfg)
                    )
                    # Build AgentMCPServerSelectedRead-like object for "all" mode
                    servers.append(
                        AgentMCPServerSelectedRead(
                            id=cfg_dict["id"],
                            agent_mcp_selection_id=selection.id,
                            reference=f"db:{cfg_dict['id']}",
                            mcp_name=cfg_dict["name"],
                            mcp_type=cfg_dict["type"],
                            mcp_description=cfg_dict.get("description"),
                            source="user",
                            is_active=cfg_dict.get("is_active", True),
                            resolved_at=datetime.now(timezone.utc),
                            created_at=cfg_dict.get("created_at"),
                            updated_at=cfg_dict.get("updated_at"),
                        )
                    )

                # Also include config MCP servers from JSON file
                config_mcps = ConfigMCPLoader.get_all_servers()
                for cfg in config_mcps:
                    servers.append(
                        AgentMCPServerSelectedRead(
                            id=f"config-{cfg['name']}",  # Synthetic ID for config MCPs
                            agent_mcp_selection_id=selection.id,
                            reference=f"config:{cfg['name']}",
                            mcp_name=cfg["name"],
                            mcp_type=cfg.get("type", "stdio"),
                            mcp_description=cfg.get("description"),
                            source="config",
                            is_active=True,
                            resolved_at=datetime.now(timezone.utc),
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                    )

            elif selection.mcp_selection_mode == "selected":
                # Get servers from related records
                servers_result = await crud_agent_mcp_server_selected.get_multi(
                    db=db,
                    agent_mcp_selection_id=selection.id,
                )

                for srv in servers_result.get("data", []):
                    srv_dict = (
                        srv.model_dump() if hasattr(srv, "model_dump") else dict(srv)
                    )

                    # Check staleness
                    if srv_dict.get("resolved_at"):
                        age_days = (
                            datetime.now(timezone.utc) - srv_dict["resolved_at"]
                        ).days
                        if age_days > STALE_THRESHOLD_DAYS:
                            logger.warning(
                                f"MCP {srv_dict['mcp_name']} metadata stale ({age_days} days old)"
                            )

                    servers.append(AgentMCPServerSelectedRead(**srv_dict))

            result = AgentMCPSelectionRead(
                id=selection.id,
                agent_id=agent_id,
                mcp_selection_mode=selection.mcp_selection_mode,
                servers=servers,
                created_at=selection.created_at,
                updated_at=selection.updated_at,
            )

            logger.debug(
                f"Successfully retrieved MCP selection for agent {agent_id}, {len(servers)} servers"
            )
            return result

        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting MCP selection: {str(e)}")
            raise

    @staticmethod
    async def update_selection(
        agent_id: str,
        user_id: str,
        selection: MCPSelection,
        db: AsyncSession,
    ) -> AgentMCPSelectionRead:
        """
        Update agent MCP selection with validation and metadata resolution.

        Atomic operation - all or nothing.

        Args:
            agent_id: Agent ID
            user_id: User ID (for ownership validation)
            selection: MCPSelection with mode and servers
            db: AsyncSession

        Returns:
            AgentMCPSelectionRead with resolved metadata

        Raises:
            NotFoundException: If agent not found
            ValueError: If validation fails (invalid references)
        """
        try:
            logger.debug(
                f"Updating MCP selection for agent {agent_id}, mode={selection.mode}"
            )

            # Verify agent exists and user owns it
            agent = await crud_agent.get(
                db=db,
                id=agent_id,
                user_id=user_id,
                is_deleted=False,
                schema_to_select=AgentRead,
                return_as_model=True,
            )

            if not agent:
                raise NotFoundException("Agent not found")

            # Validate payload
            if selection.mode not in ("all", "selected"):
                raise ValueError("Mode must be 'all' or 'selected'")

            if selection.mode == "selected" and not selection.servers:
                raise ValueError("servers list required when mode is 'selected'")

            # Validate and resolve references if in selected mode
            resolved_servers = []
            if selection.mode == "selected" and selection.servers:
                # Extract references
                references = [srv.reference for srv in selection.servers]

                # Validate all references
                await MCPReferenceValidator.validate_all_mcp_references(
                    references=references,
                    user_id=user_id,
                    db=db,
                )

                # Resolve all references to metadata
                resolved_servers = await MCPMetadataResolver.resolve_all(
                    references=references,
                    user_id=user_id,
                    db=db,
                )

            # Begin transaction
            # Get or create selection record
            result = await crud_agent_mcp_selection.get_multi(
                db=db,
                agent_id=agent_id,
                schema_to_select=AgentMCPSelectionRead,
                return_as_model=True,
                limit=1,
            )
            selection_record = result["data"][0] if result["data"] else None

            if not selection_record:
                selection_record = await crud_agent_mcp_selection.create(
                    db=db,
                    object=AgentMCPSelectionCreate(
                        agent_id=agent_id,
                        mcp_selection_mode=selection.mode,
                    ),
                )
            else:
                # Update mode
                selection_record = await crud_agent_mcp_selection.update(
                    db=db,
                    object={"mcp_selection_mode": selection.mode},
                    id=selection_record.id,
                    schema_to_select=AgentMCPSelectionRead,
                    return_as_model=True,
                )

            # Delete old servers if switching mode or updating (optional - may not exist)
            try:
                await crud_agent_mcp_server_selected.delete_multi(
                    db=db,
                    agent_mcp_selection_id=selection_record.id,
                )
            except Exception:
                # No servers to delete on first update, that's fine
                pass

            # Insert new servers with resolved metadata
            server_records = []
            if selection.mode == "selected":
                for resolved in resolved_servers:
                    server = await crud_agent_mcp_server_selected.create(
                        db=db,
                        object=AgentMCPServerSelectedCreate(
                            agent_mcp_selection_id=selection_record.id,
                            reference=resolved["reference"],
                            mcp_name=resolved["mcp_name"],
                            mcp_type=resolved["mcp_type"],
                            mcp_description=resolved.get("mcp_description"),
                            source=resolved["source"],
                            is_active=resolved.get("is_active", True),
                            resolved_at=datetime.now(timezone.utc),
                        ),
                    )
                    server_records.append(server)

            # Build response
            servers = [
                AgentMCPServerSelectedRead(
                    **{
                        "id": s.id,
                        "agent_mcp_selection_id": s.agent_mcp_selection_id,
                        "reference": s.reference,
                        "mcp_name": s.mcp_name,
                        "mcp_type": s.mcp_type,
                        "mcp_description": s.mcp_description,
                        "source": s.source,
                        "is_active": s.is_active,
                        "resolved_at": s.resolved_at,
                        "created_at": s.created_at,
                        "updated_at": s.updated_at,
                    }
                )
                for s in server_records
            ]

            result = AgentMCPSelectionRead(
                id=selection_record.id,
                agent_id=agent_id,
                mcp_selection_mode=selection.mode,
                servers=servers,
                created_at=selection_record.created_at,
                updated_at=selection_record.updated_at,
            )

            logger.info(
                f"Successfully updated MCP selection for agent {agent_id}, mode={selection.mode}, servers={len(servers)}"
            )
            return result

        except (NotFoundException, ValueError):
            raise
        except Exception as e:
            logger.error(f"Error updating MCP selection: {str(e)}")
            raise ValueError(f"Failed to update MCP selection: {str(e)}")
