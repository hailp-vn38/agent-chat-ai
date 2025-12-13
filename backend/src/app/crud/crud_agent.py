"""
CRUD operations for Agent model using FastCRUD pattern.

Methods:
- create_agent_safe: Create agent with duplicate name check
- change_agent_template: Update agent's template_id
- get_agent_by_mac_address: Get agent with device and template relations by mac_address
- Standard FastCRUD methods: create, get, get_multi, update, delete
"""

from datetime import datetime, timezone

from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.agent import Agent
from ..models.device import Device
from ..models.template import Template
from ..models.agent_template_assignment import AgentTemplateAssignment
from ..models.provider import Provider
from ..models.server_mcp_config import ServerMCPConfig
from ..schemas.agent import (
    AgentCreateInternal,
    AgentDelete,
    AgentRead,
    AgentUpdate,
    AgentUpdateInternal,
)
from ..schemas.device import DeviceRead
from ..schemas.template import TemplateRead
from ..schemas.provider import ProviderRead


logger = get_logger(__name__)


class CRUDAgent(
    FastCRUD[
        Agent,
        AgentCreateInternal,
        AgentUpdate,
        AgentUpdateInternal,
        AgentDelete,
        AgentRead,
    ]
):

    async def get_by_id(
        self,
        db: AsyncSession,
        id: str,
    ) -> AgentRead:
        agent = await self.get(
            db=db,
            id=id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )
        return agent

    async def create_agent_safe(
        self,
        db: AsyncSession,
        agent_create_internal: AgentCreateInternal,
    ) -> AgentRead:
        try:
            logger.debug(
                f"Creating agent '{agent_create_internal.agent_name}' "
                f"for user {agent_create_internal.user_id}"
            )

            # Check if agent name already exists for this user using exists()
            # exists() returns True/False without loading the full record
            name_exists = await self.exists(
                db=db,
                user_id=agent_create_internal.user_id,
                agent_name=agent_create_internal.agent_name,
                is_deleted=False,
            )

            if name_exists:
                raise ValueError(
                    f"Agent with name '{agent_create_internal.agent_name}' already exists"
                )

            # Create the agent
            agent = await self.create(
                db=db,
                object=agent_create_internal,
                return_as_model=True,
                schema_to_select=AgentRead,
            )

            logger.info(f"Agent {agent.id} created successfully")
            return agent

        except ValueError as e:
            logger.warning(f"Create validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            raise

    async def change_agent_template(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
    ) -> AgentRead:
        """
        Set the active template for an agent.

        Updates the assignment to set is_active=True and updates agent.active_template_id.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            template_id: Template UUID

        Returns:
            AgentRead: Updated agent
        """
        try:
            logger.debug(f"Changing template for agent {agent_id} to {template_id}")

            from ..crud.crud_agent_template_assignment import crud_assignment

            # Set template as active (handles deactivation of others)
            await crud_assignment.set_active_template(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            # Update agent's active_template_id
            update_data = AgentUpdateInternal(
                active_template_id=template_id,
                updated_at=datetime.now(timezone.utc),
            )

            agent_dict = await self.update(
                db=db,
                object=update_data,
                id=agent_id,
                schema_to_select=AgentRead,
                return_as_model=True,
            )

            logger.info(
                f"Agent {agent_id} template changed to {template_id} and activated"
            )
            return agent_dict

        except Exception as e:
            logger.error(f"Failed to change agent template: {str(e)}")
            raise

    async def get_agent_with_device(
        self,
        db: AsyncSession,
        agent_id: str,
        user_id: str,
    ) -> dict | None:
        """
        Get agent with bound device using left join.

        Returns agent with device nested, or None if agent not found/not owned by user.
        Device will be None if not bound.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            user_id: User UUID (ownership filter)

        Returns:
            dict: {agent: {...}, device: {...} or None} or None if not found
        """
        try:
            logger.debug(f"Fetching agent {agent_id} with device for user {user_id}")

            from fastcrud import JoinConfig

            agent_with_device = await self.get_joined(
                db=db,
                joins_config=[
                    JoinConfig(
                        model=Device,
                        join_on=Agent.device_id == Device.id,
                        join_type="left",
                    ),
                ],
                nest_joins=True,
                id=agent_id,
                user_id=user_id,  # Ownership filter
            )

            if not agent_with_device:
                logger.debug(f"Agent {agent_id} not found for user {user_id}")
                return None

            logger.info(f"Successfully fetched agent {agent_id} with device")
            return agent_with_device

        except Exception as e:
            logger.error(f"Failed to get agent {agent_id} with device: {str(e)}")
            raise

    async def get_agent_with_device_and_templates(
        self,
        db: AsyncSession,
        agent_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict | None:
        """
        Get agent with device and templates in optimized queries.

        Returns agent + device + paginated templates, or None if agent not found/not owned.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            user_id: User UUID (ownership filter)
            offset: Template list offset
            limit: Template list limit

        Returns:
            dict: {agent: {...}, device: {...}, templates: [...]} or None if not found
        """
        try:
            logger.debug(
                f"Fetching agent {agent_id} with device and templates for user {user_id}"
            )

            from fastcrud import JoinConfig

            # Get agent with device
            agent_with_device = await self.get_joined(
                db=db,
                joins_config=[
                    JoinConfig(
                        model=Device,
                        join_on=Agent.device_id == Device.id,
                        join_type="left",
                    ),
                ],
                nest_joins=True,
                id=agent_id,
                user_id=user_id,  # Ownership filter
            )

            if not agent_with_device:
                logger.debug(f"Agent {agent_id} not found for user {user_id}")
                return None

            device_data = agent_with_device.pop("device", None)

            # Get templates assigned to this agent
            from ..crud.crud_agent_template_assignment import crud_assignment
            from ..crud.crud_template import crud_template

            assignments = await crud_assignment.get_assignments_for_agent(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
            )

            # Fetch template details for each assignment
            templates = []
            for assignment in assignments.get("data", []):
                template = await crud_template.get(
                    db=db,
                    id=assignment.template_id,
                    is_deleted=False,
                    schema_to_select=TemplateRead,
                    return_as_model=True,
                )
                if template:
                    templates.append(template)

            logger.info(
                f"Successfully fetched agent {agent_id} with device and templates"
            )

            return {
                "agent": AgentRead(**agent_with_device),
                "device": (
                    DeviceRead(**device_data) if device_data is not None else None
                ),
                "templates": templates,
            }

        except Exception as e:
            logger.error(
                f"Failed to get agent {agent_id} with device and templates: {str(e)}"
            )
            raise

    async def get_agent_by_mac_address(
        self,
        db: AsyncSession,
        mac_address: str,
    ) -> dict | None:
        """
        Get agent by device mac_address (for WebSocket connection).

        Returns agent with device, template, and provider configs for module initialization.

        Args:
            db: AsyncSession
            mac_address: Device MAC address

        Returns:
            dict: Agent with device, template, and providers nested:
                {
                    "id": "agent-uuid",
                    "device": {...},
                    "template": {...},
                    "providers": {
                        "ASR": {"type": "sherpa", "config": {...}} or None,
                        "LLM": {"type": "openai", "config": {...}} or None,
                        ...
                    }
                }
        """
        try:
            logger.debug(f"Fetching agent by mac_address: {mac_address}")

            agent_dict = await self.get_joined(
                db=db,
                join_model=Device,
                join_on=Agent.device_id == Device.id,
                join_type="left",
                nest_joins=True,
                device_mac_address=mac_address,
            )

            if not agent_dict:
                logger.warning(f"Agent with mac_address {mac_address} not found")
                return None

            # Get template with provider details using new Template model
            if agent_dict.get("active_template_id"):
                from ..crud.crud_template import crud_template

                template_dict = await crud_template.get(
                    db, id=agent_dict.get("active_template_id")
                )
                if template_dict:
                    agent_dict["template"] = template_dict

                    # Fetch provider details for each category
                    agent_dict["providers"] = await self._fetch_template_providers(
                        db, template_dict
                    )
            else:
                agent_dict["providers"] = {}

            # Fetch user MCP configs
            agent_dict["mcp_configs"] = await self._fetch_user_mcp_configs(
                db=db,
                user_id=agent_dict.get("user_id"),
                agent_id=agent_dict.get("id"),
            )

            logger.info(f"Successfully fetched agent by mac_address: {mac_address}")

            return agent_dict

        except Exception as e:
            logger.error(f"Failed to get agent by mac_address: {str(e)}")
            raise

    async def _fetch_user_mcp_configs(
        self,
        db: AsyncSession,
        user_id: str,
        agent_id: str | None = None,
    ) -> list[dict]:
        """
        Fetch user's active MCP configs from normalized selection tables.

        Uses AgentMCPSelectionService to get selection with resolved metadata
        in a single efficient query. Automatically handles both 'all' and 'selected' modes.

        Returns MCP configs in format expected by ServerMCPManager.

        Args:
            db: AsyncSession
            user_id: User UUID
            agent_id: Agent UUID

        Returns:
            list[dict]: List of MCP configs in format expected by ServerMCPManager
        """
        from ..services.agent_mcp_selection_service import AgentMCPSelectionService

        try:
            if not agent_id:
                logger.debug("agent_id not provided, returning empty configs")
                return []

            logger.debug(f"Fetching MCP configs for agent {agent_id}, user {user_id}")

            # Use AgentMCPSelectionService to get selection with resolved metadata
            selection = await AgentMCPSelectionService.get_selection(
                agent_id=agent_id,
                user_id=user_id,
                db=db,
            )

            # Convert resolved servers to MCP config format
            mcp_configs = []
            for server in selection.servers:
                cfg_type = server.mcp_type
                mcp_config = {
                    "id": server.id,
                    "name": server.mcp_name,
                    "type": cfg_type,
                    "description": server.mcp_description,
                    "source": server.source,
                    "reference": server.reference,
                }

                # Extract actual MCP config ID from reference (format: "db:{uuid}")
                mcp_config_id = None
                if server.reference and server.reference.startswith("db:"):
                    mcp_config_id = server.reference[3:]  # Remove "db:" prefix

                # Add type-specific fields based on metadata
                # For stdio, fetch from config
                if cfg_type == "stdio":
                    if server.source == "user" and mcp_config_id:
                        # Get full config from database for user-defined stdio
                        from ..crud.crud_server_mcp_config import (
                            crud_server_mcp_config,
                        )

                        config = await crud_server_mcp_config.get(
                            db=db,
                            id=mcp_config_id,
                            user_id=user_id,
                        )
                        if config:
                            mcp_config["command"] = config.get("command")
                            mcp_config["args"] = config.get("args")
                            mcp_config["env"] = config.get("env")

                    elif server.source == "config":
                        # Get config from JSON file for system MCP
                        from ..services.config_mcp_loader import ConfigMCPLoader

                        config_mcp = ConfigMCPLoader.get_server(server.mcp_name)
                        if config_mcp:
                            mcp_config["command"] = config_mcp.get("command")
                            mcp_config["args"] = config_mcp.get("args")
                            mcp_config["env"] = config_mcp.get("env")

                elif cfg_type in ("sse", "http"):
                    if server.source == "user" and mcp_config_id:
                        # For user-defined SSE/HTTP, fetch from config
                        from ..crud.crud_server_mcp_config import (
                            crud_server_mcp_config,
                        )

                        config = await crud_server_mcp_config.get(
                            db=db,
                            id=mcp_config_id,
                            user_id=user_id,
                        )
                        if config:
                            mcp_config["url"] = config.get("url")
                            mcp_config["headers"] = config.get("headers")

                    elif server.source == "config":
                        # Get config from JSON file for system MCP
                        from ..services.config_mcp_loader import ConfigMCPLoader

                        config_mcp = ConfigMCPLoader.get_server(server.mcp_name)
                        if config_mcp:
                            mcp_config["url"] = config_mcp.get("url")
                            mcp_config["headers"] = config_mcp.get("headers")
                            # Preserve original transport for special handling
                            if config_mcp.get("_transport"):
                                mcp_config["transport"] = config_mcp.get("_transport")

                mcp_configs.append(mcp_config)

            logger.debug(f"Returning {len(mcp_configs)} MCP configs")
            return mcp_configs

        except Exception as e:
            logger.warning(
                f"Failed to fetch MCP configs for agent {agent_id}, user {user_id}: {e}"
            )
            return []

    async def _fetch_template_providers(
        self,
        db: AsyncSession,
        template_dict: dict,
    ) -> dict:
        """
        Fetch provider details for template's provider references.

        Supports reference formats:
        - "db:{uuid}" - fetch from database
        - "config:{name}" - skip (handled by module_factory from config.yml)
        - Plain UUID - backward compat, fetch from database

        Args:
            db: AsyncSession
            template_dict: Template dict with provider reference fields (ASR, LLM, etc.)

        Returns:
            dict: Provider configs by category:
                {
                    "ASR": {"id": "...", "type": "sherpa", "config": {...}} or None,
                    "LLM": {"id": "...", "type": "openai", "config": {...}} or None,
                    ...
                }
        """
        from ..crud.crud_provider import crud_provider
        from ..ai.module_factory import parse_provider_reference

        provider_categories = ["ASR", "LLM", "VLLM", "TTS", "Memory", "Intent"]
        providers = {}

        # Collect all provider IDs that need to be fetched from DB
        provider_ids = []
        id_to_category = {}

        for category in provider_categories:
            ref = template_dict.get(category)
            if not ref:
                continue

            # Parse reference to get source and value
            parsed = parse_provider_reference(ref)
            if parsed is None:
                logger.debug(f"[{category}] Invalid reference format: {ref}")
                continue

            source, value = parsed
            if source == "db":
                # Only fetch from DB if it's a db: reference
                provider_ids.append(value)
                id_to_category[value] = category
                logger.debug(f"[{category}] Will fetch from DB: {value}")
            else:
                # config: references are handled by module_factory
                logger.debug(f"[{category}] Skipping config reference: {ref}")

        if not provider_ids:
            logger.debug("No DB provider IDs to fetch")
            return {cat: None for cat in provider_categories}

        # Batch fetch providers from DB
        try:
            logger.debug(f"Fetching providers from DB: {provider_ids}")
            result = await crud_provider.get_multi(
                db=db,
                id__in=provider_ids,
                is_deleted=False,
                schema_to_select=ProviderRead,
                return_as_model=True,
            )
            fetched_providers = result.get("data", [])
            logger.debug(f"Fetched {len(fetched_providers)} providers from DB")

            # Map providers by ID (as string for comparison)
            provider_map = {str(p.id): p for p in fetched_providers}

            for category in provider_categories:
                ref = template_dict.get(category)
                if not ref:
                    providers[category] = None
                    continue

                parsed = parse_provider_reference(ref)
                if parsed is None:
                    providers[category] = None
                    continue

                source, value = parsed
                if source == "db" and value in provider_map:
                    provider = provider_map[value]
                    providers[category] = {
                        "id": str(provider.id),
                        "name": provider.name,
                        "type": provider.type,
                        "config": provider.config,
                    }
                    logger.debug(
                        f"[{category}] ✅ Provider loaded from DB: {provider.name}"
                    )
                else:
                    providers[category] = None

        except Exception as e:
            logger.warning(f"Failed to fetch providers: {e}, returning empty")
            providers = {cat: None for cat in provider_categories}

        return providers

    async def get_list_agent_template(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """
        Get templates assigned to agent.

        Uses new assignment-based template system.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            offset: List offset
            limit: List limit

        Returns:
            dict: {data: [...], total_count: int, offset: int, limit: int}
        """
        try:
            logger.debug(
                f"Fetching agent templates for agent_id: {agent_id}, "
                f"offset: {offset}, limit: {limit}"
            )

            from ..crud.crud_agent_template_assignment import crud_assignment
            from ..crud.crud_template import crud_template

            # Get assignments for agent
            assignments = await crud_assignment.get_assignments_for_agent(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
            )

            # Fetch template details for each assignment
            templates_data = []
            for assignment in assignments.get("data", []):
                template = await crud_template.get(
                    db=db,
                    id=assignment.template_id,
                    is_deleted=False,
                    schema_to_select=TemplateRead,
                    return_as_model=True,
                )
                if template:
                    templates_data.append(template)

            total_count = assignments.get("total_count", 0)

            return {
                "data": templates_data,
                "total_count": total_count,
                "offset": offset,
                "limit": limit,
            }

        except Exception as e:
            logger.error(f"Failed to get agent templates for agent_id: {str(e)}")
            raise

    async def get_detail_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """
        Get agent detail with device and templates (kept for backward compatibility).

        Deprecated: Use get_agent_with_device_and_templates() instead.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            offset: Template list offset
            limit: Template list limit

        Returns:
            dict: {agent: {...}, device: {...}, templates: [...]}
        """
        try:
            logger.debug(f"Fetching agent {agent_id} with device and templates")
            from fastcrud import JoinConfig

            # Query 1: Get agent with device using get_joined with nest_joins=True result dict
            agent_with_device = await self.get_joined(
                db=db,
                joins_config=[
                    JoinConfig(
                        model=Device,
                        join_on=Agent.device_id == Device.id,
                        join_type="left",
                    ),
                ],
                nest_joins=True,
                id=agent_id,
            )
            if not agent_with_device:
                logger.warning(f"Agent with id {agent_id} not found")
                return {"agent": None, "device": None, "templates": []}

            device_data = agent_with_device.pop("device", None)

            # Get templates assigned to this agent
            from ..crud.crud_agent_template_assignment import crud_assignment
            from ..crud.crud_template import crud_template

            assignments = await crud_assignment.get_assignments_for_agent(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
            )

            templates = []
            for assignment in assignments.get("data", []):
                template = await crud_template.get(
                    db=db,
                    id=assignment.template_id,
                    is_deleted=False,
                    schema_to_select=TemplateRead,
                    return_as_model=True,
                )
                if template:
                    templates.append(template)
            logger.debug(
                f"Successfully fetched agent {agent_id} with device and templates"
            )

            # Pydantic schema will auto-convert UUID objects to strings
            return {
                "agent": AgentRead(**agent_with_device),
                "device": (
                    DeviceRead(**device_data) if device_data is not None else None
                ),
                "templates": templates,
            }
        except Exception as e:
            logger.error(
                f"Failed to get agent {agent_id} with device and templates: {str(e)}"
            )
            raise


crud_agent = CRUDAgent(Agent)
