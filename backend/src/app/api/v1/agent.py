"""Agent API router.

Exposes endpoints to list/create/update/delete agents, manage their template assignments,
and bind or unbind IoT devices for the authenticated user.

Architecture:
- API layer handles HTTP validation and error formatting
- CRUD layer handles database operations with full error handling
- Dependencies validate user permissions (current_user) and resource existence

Template Management:
- Use POST /agents/{id}/templates/{template_id} to assign templates
- Use DELETE /agents/{id}/templates/{template_id} to unassign templates
- Use PUT /agents/{id}/activate-template/{template_id} to set active template
- Template CRUD operations are in /templates endpoints
"""

from datetime import datetime, timezone as dt_timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse, SuccessResponse

from ...api.dependencies import get_current_user, get_cache_manager_dependency
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    ForbiddenException,
    NotFoundException,
)
from ...core.logger import get_logger
from ...core.utils.cache import CacheKey, BaseCacheManager
from ...models.agent import Agent
from ...models.agent import _generate_api_key
from ...crud.crud_agent import crud_agent
from ...crud.crud_template import crud_template
from ...crud.crud_agent_template_assignment import crud_assignment
from ...crud.crud_device import crud_device
from ...crud.crud_provider import crud_provider
from ...schemas.agent import (
    AgentCreate,
    AgentCreateInternal,
    AgentRead,
    AgentUpdate,
    AgentUpdateInternal,
    BindDeviceRequest,
    AgentWithDeviceAndTemplatesRead,
    WebhookConfig,
    AgentWebhookRead,
    WebhookNotificationPayload,
)
from ...schemas.template import (
    TemplateRead,
    TemplateWithProvidersRead,
)
from ...schemas.device import DeviceRead
from ...schemas.agent_template_assignment import AssignmentRead
from ...ai.module_factory import parse_provider_reference
from ...config import load_config
from ...services.openmemory import get_openmemory_service, OpenMemoryError
from ...services.agent_service import agent_service
from ...services.mqtt_service import MQTTService

logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ========== Helper Functions ==========


async def verify_agent_ownership(
    db: AsyncSession,
    agent_id: str,
    user_id: str,
) -> AgentRead:
    """
    Return the requested agent if it belongs to the provided user.

    Args:
        db: AsyncSession
        agent_id: UUID of agent
        user_id: UUID of user

    Returns:
        AgentRead: Persisted agent data

    Raises:
        NotFoundException: If the agent does not exist for the user
    """
    agent = await crud_agent.get(
        db=db,
        id=agent_id,
        user_id=user_id,
        schema_to_select=AgentRead,
        return_as_model=True,
    )

    if not agent:
        raise NotFoundException(f"Agent {agent_id} not found")

    return agent


# Provider categories mapping for validation
PROVIDER_CATEGORIES = {
    "ASR": "ASR",
    "LLM": "LLM",
    "VLLM": "VLLM",
    "TTS": "TTS",
    "Memory": "Memory",
    "Intent": "Intent",
}


async def _enrich_templates_with_providers(
    db: AsyncSession,
    templates: list,
) -> list[dict]:
    """
    Enrich templates with full provider info (reference, name, type, source).

    Handles both config and db provider references.

    Args:
        db: AsyncSession
        templates: List of TemplateRead models or dicts

    Returns:
        list[dict]: Templates with provider info instead of just references
    """
    if not templates:
        return []

    provider_fields = ["ASR", "LLM", "VLLM", "TTS", "Memory", "Intent"]

    # Collect all unique db provider IDs from templates
    db_provider_ids: set[str] = set()
    config_providers: dict[str, set] = {}
    config = None  # Lazy load

    for template in templates:
        template_dict = (
            template.model_dump() if hasattr(template, "model_dump") else template
        )
        for field in provider_fields:
            reference = template_dict.get(field)
            if reference:
                parsed = parse_provider_reference(reference)
                if parsed:
                    source, value = parsed
                    if source == "db":
                        db_provider_ids.add(value)
                    elif source == "config":
                        if field not in config_providers:
                            config_providers[field] = set()
                        config_providers[field].add(value)

    # Batch fetch all db providers
    db_providers_map: dict[str, dict] = {}
    for provider_id in db_provider_ids:
        provider = await crud_provider.get(db=db, id=provider_id, is_deleted=False)
        if provider:
            db_providers_map[provider_id] = {
                "reference": f"db:{provider.get('id')}",
                "id": provider.get("id"),
                "name": provider.get("name"),
                "type": provider.get("type"),
                "source": "user",
            }

    # Load config if needed
    if config_providers:
        try:
            config = load_config()
        except Exception:
            config = {}

    # Enrich templates
    enriched_templates = []
    for template in templates:
        template_dict = (
            template.model_dump() if hasattr(template, "model_dump") else dict(template)
        )

        for field in provider_fields:
            reference = template_dict.get(field)
            if not reference:
                template_dict[field] = None
                continue

            parsed = parse_provider_reference(reference)
            if not parsed:
                template_dict[field] = None
                continue

            source, value = parsed

            if source == "db" and value in db_providers_map:
                template_dict[field] = db_providers_map[value]
            elif source == "config" and config:
                category = PROVIDER_CATEGORIES.get(field, field)
                if category in config and value in config[category]:
                    cfg = config[category][value]
                    provider_type = (
                        cfg.get("type", value) if isinstance(cfg, dict) else value
                    )
                    template_dict[field] = {
                        "reference": f"config:{value}",
                        "name": value,
                        "type": provider_type,
                        "source": "default",
                    }
                else:
                    template_dict[field] = None
            else:
                template_dict[field] = None

        enriched_templates.append(template_dict)

    return enriched_templates


# ========== Agent CRUD Endpoints ==========


@router.get("", response_model=PaginatedResponse[AgentRead])
async def list_agents(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    Return a paginated list of agents that belong to the current user.

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=10)

    Returns:
        PaginatedResponse[AgentRead]: Structured pagination payload
    """
    try:
        logger.debug(f"Listing agents for user {current_user['id']}")

        agents_data = await crud_agent.get_multi(
            db=db,
            user_id=current_user["id"],
            is_deleted=False,
            offset=(page - 1) * page_size,
            limit=page_size,
            schema_to_select=AgentRead,
        )

        total = agents_data.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            success=True,
            message="Success",
            data=agents_data["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=AgentRead, status_code=201)
async def create_agent(
    agent: AgentCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AgentRead:
    """
    Create an agent for the authenticated user.

    Body:
        AgentCreate: Includes agent_name, description, and optional status

    Returns:
        AgentRead: Newly created agent

    Raises:
        HTTPException: 400 if validation fails (for example duplicate name)
    """
    try:
        logger.info(
            f"Creating agent '{agent.agent_name}' for user {current_user['id']}"
        )

        agent_create_internal = AgentCreateInternal(
            **agent.model_dump(),
            user_id=current_user["id"],
        )

        created_agent = await crud_agent.create_agent_safe(
            db=db,
            agent_create_internal=agent_create_internal,
        )

        logger.info(f"Successfully created agent {created_agent.id}")
        return created_agent

    except ValueError as e:
        logger.warning(f"Create validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}", response_model=AgentWithDeviceAndTemplatesRead)
async def get_agent_detail(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AgentWithDeviceAndTemplatesRead:
    """
    Retrieve agent details together with bound device information and templates.

    Templates include full provider info (id, name, type) for ASR, LLM, VLLM, TTS, Memory, Intent.

    Returns:
        AgentWithDeviceAndTemplatesRead: Aggregated agent data with provider details

    Raises:
        NotFoundException: If the agent does not exist for this user
    """
    try:
        logger.debug(f"Fetching detail for agent {agent_id}")

        result = await crud_agent.get_agent_with_device_and_templates(
            db=db,
            agent_id=agent_id,
            user_id=current_user["id"],
            offset=0,
            limit=100,
        )

        if not result:
            raise NotFoundException(f"Agent {agent_id} not found")

        templates = result.get("templates", [])
        enriched_templates = await _enrich_templates_with_providers(db, templates)
        result["templates"] = enriched_templates

        logger.debug(f"Agent detail retrieved: {agent_id}")
        return AgentWithDeviceAndTemplatesRead(**result)

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent detail: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: str,
    agent_update: AgentUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AgentRead:
    """
    Update fields on the agent that belongs to the current user.

    Body:
        AgentUpdate: Partial payload with optional agent_name, description, status

    Returns:
        AgentRead: Updated agent data

    Raises:
        NotFoundException: If the agent does not exist for this user
    """
    try:
        logger.debug(f"Updating agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        update_data = AgentUpdateInternal(
            **agent_update.model_dump(exclude_unset=True),
            updated_at=datetime.now(dt_timezone.utc),
        )

        updated_agent = await crud_agent.update(
            db=db,
            object=update_data,
            id=agent_id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )

        logger.info(f"Agent {agent_id} updated successfully")
        return updated_agent

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """
    Delete the agent after verifying ownership and remove any bound device.

    Also deletes all memories associated with this agent from OpenMemory.

    Raises:
        NotFoundException: If the agent does not exist for this user
    """
    try:
        logger.info(f"Deleting agent {agent_id}")

        agent = await verify_agent_ownership(db, agent_id, current_user["id"])

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Delete all memories from OpenMemory
        try:
            openmemory_service = get_openmemory_service()
            await openmemory_service.delete_user_memories(agent_id=agent_id)
            logger.info(f"Deleted all memories for agent {agent_id} from OpenMemory")
        except OpenMemoryError as e:
            logger.warning(f"Failed to delete memories from OpenMemory: {str(e)}")
        except Exception as e:
            logger.warning(f"Unexpected error deleting memories: {str(e)}")

        if agent.device_id:
            logger.debug(f"Deleting device {agent.device_id} bound to agent {agent_id}")
            await crud_device.db_delete(db=db, id=agent.device_id)
            logger.info(f"Device {agent.device_id} deleted")

        await crud_agent.db_delete(db=db, id=agent_id)

        logger.info(f"Agent {agent_id} deleted successfully")

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ========== Device Binding Endpoints ==========


@router.post("/{agent_id}/bind-device", response_model=DeviceRead, status_code=200)
async def bind_device(
    agent_id: str,
    bind_request: BindDeviceRequest,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    cache: Annotated[BaseCacheManager, Depends(get_cache_manager_dependency)],
) -> DeviceRead:
    """
    Bind an IoT device to the specified agent using an activation code stored in cache.

    Flow:
    1. Verify the agent belongs to the current user
    2. Resolve the activation code to a mac_address from Redis
    3. Read the device payload from Redis
    4. Create or update the device and link it to the agent
    5. Clear activation cache entries

    Returns:
        DeviceRead: Created or updated device bound to the agent

    Raises:
        HTTPException: 400 if the activation data is missing or invalid
        NotFoundException: If the agent does not exist for this user
    """
    try:
        logger.info(
            f"Binding device to agent {agent_id} with code: {bind_request.code}"
        )

        agent = await verify_agent_ownership(db, agent_id, current_user["id"])

        mac_address = await cache.get(CacheKey.ACTIVATION_CODE, bind_request.code)
        if not mac_address:
            logger.warning(f"Activation code {bind_request.code} not found or expired")
            raise HTTPException(
                status_code=400,
                detail="Activation code not found or expired",
            )

        logger.debug(
            f"Retrieved mac_address: {mac_address} for code: {bind_request.code}"
        )

        device_data = await cache.get(CacheKey.DEVICE_ACTIVATION, mac_address)
        if not device_data:
            logger.warning(f"Device data not found for mac_address: {mac_address}")
            raise HTTPException(
                status_code=400,
                detail="Device data not found in activation cache",
            )

        logger.debug(f"Retrieved device data for mac: {mac_address}")

        try:
            device = await crud_device.bind_device_safe(
                db=db,
                mac_address=mac_address,
                user_id=current_user["id"],
                agent_id=agent_id,
                device_data=device_data,
            )
        except ValueError as e:
            logger.warning(f"Device binding validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

        if not agent.device_id:
            logger.debug(f"Updating agent {agent_id} device_id to {device.id}")
            update_data = AgentUpdateInternal(
                device_id=device.id,
                device_mac_address=mac_address,
                updated_at=datetime.now(dt_timezone.utc),
            )
            await crud_agent.update(
                db=db,
                object=update_data,
                id=agent_id,
                schema_to_select=AgentRead,
                return_as_model=True,
            )
            logger.info(f"Agent {agent_id} device_id updated to {device.id}")

        try:
            await cache.delete(CacheKey.ACTIVATION_CODE, bind_request.code)
            await cache.delete(CacheKey.DEVICE_ACTIVATION, mac_address)
            logger.debug(f"Cleaned up Redis cache for code: {bind_request.code}")
        except Exception as e:
            logger.warning(f"Failed to clean up cache: {str(e)}")

        logger.info(f"Device {device.id} bound to agent {agent_id}")
        return device

    except NotFoundException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error binding device: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}/device", status_code=204)
async def delete_device_from_agent(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """
    Unbind the current device from the agent and delete the device record.

    Flow:
    1. Verify the agent belongs to the current user
    2. Ensure a device_id is present on the agent
    3. Delete the device and clear the agent's device metadata

    Raises:
        HTTPException: 404 when no device is bound to the agent
        NotFoundException: If the agent does not exist for this user
    """
    try:
        logger.info(f"Deleting device from agent {agent_id}")

        agent = await verify_agent_ownership(db, agent_id, current_user["id"])

        if not agent.device_id:
            logger.warning(f"Agent {agent_id} has no device bound")
            raise HTTPException(
                status_code=404,
                detail="No device bound to this agent",
            )

        device_id = agent.device_id
        logger.debug(
            f"Agent {agent_id} has device {device_id}, proceeding with deletion"
        )

        await crud_device.db_delete(db=db, id=device_id)
        logger.info(f"Device {device_id} hard deleted from database")

        update_data = AgentUpdateInternal(
            device_mac_address=None,
            updated_at=datetime.now(dt_timezone.utc),
        )
        await crud_agent.update(
            db=db,
            object=update_data,
            id=agent_id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )
        logger.info(f"Agent {agent_id} device_mac_address cleared")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device from agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ========== Agent Template Assignment Endpoints ==========


@router.get(
    "/{agent_id}/templates", response_model=PaginatedResponse[TemplateWithProvidersRead]
)
async def get_agent_templates(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    Return a paginated list of templates assigned to the given agent.

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=10)

    Returns:
        PaginatedResponse[TemplateWithProvidersRead]: Paginated templates with provider details
    """
    try:
        logger.debug(f"Listing templates for agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        assignments = await crud_assignment.get_assignments_for_agent(
            db=db,
            agent_id=agent_id,
            offset=(page - 1) * page_size,
            limit=page_size,
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

        total = assignments.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size

        enriched_templates = await _enrich_templates_with_providers(db, templates)

        return PaginatedResponse(
            success=True,
            message="Success",
            data=enriched_templates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error listing agent templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{agent_id}/templates/{template_id}",
    response_model=SuccessResponse[AssignmentRead],
    status_code=201,
)
async def assign_template_to_agent(
    agent_id: str,
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    set_active: Annotated[bool, Query()] = False,
) -> dict:
    """
    Assign a template to the agent.

    User must own the agent. User must own the template OR template must be public.

    Query Parameters:
    - set_active: bool (default=False) - Set as active template for agent

    Returns:
        SuccessResponse[AssignmentRead]: Created assignment

    Raises:
        NotFoundException: If agent or template not found
        ForbiddenException: If user cannot access template
    """
    try:
        logger.info(f"Assigning template {template_id} to agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        can_access = await crud_template.can_access_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
        )

        if not can_access:
            template = await crud_template.get(db=db, id=template_id, is_deleted=False)
            if not template:
                raise NotFoundException(f"Template {template_id} not found")
            raise ForbiddenException("You do not have access to this template")

        assignment = await crud_assignment.assign_template_to_agent(
            db=db,
            agent_id=agent_id,
            template_id=template_id,
            set_active=set_active,
        )

        if set_active:
            update_data = AgentUpdateInternal(
                active_template_id=template_id,
                updated_at=datetime.now(dt_timezone.utc),
            )
            await crud_agent.update(db=db, object=update_data, id=agent_id)
            logger.info(f"Set template {template_id} as active for agent {agent_id}")

        logger.info(f"Template {template_id} assigned to agent {agent_id}")

        return SuccessResponse(
            success=True,
            message="Template assigned successfully",
            data=assignment,
        )

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except Exception as e:
        logger.error(f"Error assigning template to agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}/templates/{template_id}", status_code=204)
async def unassign_template_from_agent(
    agent_id: str,
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """
    Unassign a template from the agent.

    If this was the active template, clears agent's active_template_id.

    Raises:
        NotFoundException: If agent or assignment not found
    """
    try:
        logger.info(f"Unassigning template {template_id} from agent {agent_id}")

        agent = await verify_agent_ownership(db, agent_id, current_user["id"])

        removed = await crud_assignment.unassign_template_from_agent(
            db=db,
            agent_id=agent_id,
            template_id=template_id,
        )

        if not removed:
            raise NotFoundException(
                f"Template {template_id} not assigned to agent {agent_id}"
            )

        if agent.active_template_id == template_id:
            update_data = AgentUpdateInternal(
                active_template_id=None,
                updated_at=datetime.now(dt_timezone.utc),
            )
            await crud_agent.update(db=db, object=update_data, id=agent_id)
            logger.info(f"Cleared active template for agent {agent_id}")

        logger.info(f"Template {template_id} unassigned from agent {agent_id}")

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error unassigning template from agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{agent_id}/activate-template/{template_id}", response_model=AgentRead)
async def activate_agent_template(
    agent_id: str,
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AgentRead:
    """
    Set the provided template as the active template for the agent.

    The template must be assigned to the agent or accessible to the user.
    If not assigned, it will be auto-assigned.

    Returns:
        AgentRead: Agent with updated active_template_id

    Raises:
        NotFoundException: If the agent or template does not exist
        ForbiddenException: If user cannot access the template
    """
    try:
        logger.info(f"Activating template {template_id} for agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        can_access = await crud_template.can_access_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
        )

        if not can_access:
            template = await crud_template.get(db=db, id=template_id, is_deleted=False)
            if not template:
                raise NotFoundException(f"Template {template_id} not found")
            raise HTTPException(
                status_code=403, detail="You do not have access to this template"
            )

        assignment = await crud_assignment.get(
            db=db,
            agent_id=agent_id,
            template_id=template_id,
        )

        if not assignment:
            await crud_assignment.assign_template_to_agent(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
                set_active=True,
            )
        else:
            await crud_assignment.set_active_template(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

        update_data = AgentUpdateInternal(
            active_template_id=template_id,
            updated_at=datetime.now(dt_timezone.utc),
        )
        updated_agent = await crud_agent.update(
            db=db,
            object=update_data,
            id=agent_id,
            schema_to_select=AgentRead,
            return_as_model=True,
        )

        logger.info(f"Agent {agent_id} active template set to {template_id}")
        return updated_agent

    except NotFoundException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating agent template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ========== Agent Message Endpoints ==========


@router.get("/{agent_id}/messages")
async def get_agent_messages(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """
    Return paginated chat messages for an agent.

    Messages are ordered by created_at DESC (newest first).

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=50)

    Returns:
        PaginatedResponse with AgentMessageRead items
    """
    try:
        logger.debug(f"Listing messages for agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        from ...services.agent_service import agent_service

        result = await agent_service.get_chat_history(
            db=db,
            agent_id=agent_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        total = result.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return PaginatedResponse(
            success=True,
            message="Success",
            data=result["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error listing agent messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}/messages/sessions")
async def get_agent_sessions(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """
    Return list of chat sessions for an agent.

    Each session includes first/last message timestamp and message count.
    Sessions are ordered by last_message_at DESC (most recent first).

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=20)

    Returns:
        PaginatedResponse with SessionSummary items
    """
    try:
        logger.debug(f"Listing sessions for agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        from ...services.agent_service import agent_service

        result = await agent_service.get_chat_sessions(
            db=db,
            agent_id=agent_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        total = result.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return PaginatedResponse(
            success=True,
            message="Success",
            data=result["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error listing agent sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}/messages/{session_id}")
async def get_session_messages(
    agent_id: str,
    session_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, Any]:
    """
    Return messages for a specific chat session.

    Messages are ordered by created_at ASC (conversation order).

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=100)

    Returns:
        PaginatedResponse with AgentMessageRead items
    """
    try:
        logger.debug(f"Getting session {session_id} for agent {agent_id}")

        await verify_agent_ownership(db, agent_id, current_user["id"])

        from ...services.agent_service import agent_service

        result = await agent_service.get_chat_session(
            db=db,
            agent_id=agent_id,
            session_id=session_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        total = result.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return PaginatedResponse(
            success=True,
            message="Success",
            data=result["data"],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error getting session messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}/messages")
async def delete_agent_messages(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    session_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """
    Delete chat messages for an agent.

    If session_id is provided, only deletes messages for that session.
    Otherwise, deletes all messages for the agent.

    Query Parameters:
    - session_id: Optional session UUID to delete specific session

    Returns:
        SuccessResponse with deleted_count
    """
    try:
        logger.info(
            f"Deleting messages for agent {agent_id}"
            + (f", session {session_id}" if session_id else "")
        )

        await verify_agent_ownership(db, agent_id, current_user["id"])

        from ...services.agent_service import agent_service
        from ...schemas.agent_message import AgentMessageDelete

        deleted_count = await agent_service.delete_chat_history(
            db=db,
            agent_id=agent_id,
            session_id=session_id,
        )

        logger.info(f"Deleted {deleted_count} messages for agent {agent_id}")

        return SuccessResponse(
            success=True,
            message=f"Deleted {deleted_count} messages",
            data=AgentMessageDelete(deleted_count=deleted_count).model_dump(),
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ========== Webhook Configuration Endpoints ==========


@router.get("/{agent_id}/webhook-config", response_model=SuccessResponse[WebhookConfig])
async def get_webhook_config(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get webhook API key for an agent.

    Returns the API key if it exists.

    Path Parameters:
    - agent_id: Agent UUID

    Returns:
        SuccessResponse containing WebhookConfig with api_key
        Returns None for api_key if not yet generated

    Raises:
        404: If agent not found
        403: If user doesn't own the agent
    """
    try:
        # Verify ownership
        agent_check = await verify_agent_ownership(db, agent_id, current_user["id"])

        # Get agent with api_key using AgentWebhookRead schema
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            user_id=current_user["id"],
            schema_to_select=AgentWebhookRead,
            return_as_model=True,
        )

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        webhook_config = WebhookConfig(
            agent_id=agent_id,
            api_key=agent.api_key,
        )

        return SuccessResponse(data=webhook_config).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook config for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{agent_id}/webhook-config", response_model=SuccessResponse[WebhookConfig]
)
async def create_webhook_config(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Generate a new webhook API key for an agent.

    Creates a unique API key for webhook authentication.
    If an existing key is present, it will be replaced.

    Path Parameters:
    - agent_id: Agent UUID

    Returns:
        SuccessResponse containing WebhookConfig with newly generated api_key

    Raises:
        404: If agent not found
        403: If user doesn't own the agent
    """
    try:
        # Verify ownership
        agent_check = await verify_agent_ownership(db, agent_id, current_user["id"])

        # Generate new API key
        new_api_key = _generate_api_key()

        # Get agent by id and user_id
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            user_id=current_user["id"],
            schema_to_select=AgentWebhookRead,
            return_as_model=True,
        )

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # We need to get the actual Agent model object to update it
        # Query using direct SQLAlchemy
        from sqlalchemy import select as sa_select

        stmt = sa_select(Agent).where(
            Agent.id == agent_id,
            Agent.user_id == current_user["id"],
            Agent.is_deleted == False,
        )
        result = await db.execute(stmt)
        agent_obj = result.scalar_one_or_none()

        if not agent_obj:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Update api_key
        agent_obj.api_key = new_api_key
        db.add(agent_obj)
        await db.commit()

        webhook_config = WebhookConfig(
            agent_id=agent_id,
            api_key=new_api_key,
        )

        logger.info(f"Generated new webhook API key for agent {agent_id}")

        return SuccessResponse(
            success=True,
            message="Webhook API key generated successfully",
            data=webhook_config,
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error creating webhook config for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}/webhook-config")
async def delete_webhook_config(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Delete webhook API key for an agent.

    Removes the API key, disabling webhook authentication.

    Path Parameters:
    - agent_id: Agent UUID

    Returns:
        SuccessResponse with success message

    Raises:
        404: If agent not found
        403: If user doesn't own the agent
    """
    try:
        # Verify ownership
        agent_check = await verify_agent_ownership(db, agent_id, current_user["id"])

        # Get agent by id and user_id
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            user_id=current_user["id"],
            schema_to_select=AgentWebhookRead,
            return_as_model=True,
        )

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # We need to get the actual Agent model object to update it
        # Query using direct SQLAlchemy
        from sqlalchemy import select as sa_select

        stmt = sa_select(Agent).where(
            Agent.id == agent_id,
            Agent.user_id == current_user["id"],
            Agent.is_deleted == False,
        )
        result = await db.execute(stmt)
        agent_obj = result.scalar_one_or_none()

        if not agent_obj:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Remove api_key
        agent_obj.api_key = None
        db.add(agent_obj)
        await db.commit()

        logger.info(f"Deleted webhook API key for agent {agent_id}")

        return SuccessResponse(
            success=True,
            message="Webhook API key deleted successfully",
            data=None,
        ).model_dump()

    except NotFoundException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook config for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{agent_id}/webhook")
async def webhook_handler(
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    request: Request,
    token: Annotated[str | None, Query()] = None,
    x_agent_token: Annotated[str | None, Header(alias="x-agent-token")] = None,
) -> dict[str, Any]:
    """
    Webhook endpoint for external systems to push notifications to an agent's device.

    Authenticates incoming requests using the agent's API key and processes
    notification payloads. The API key can be provided via:
    - Query parameter: ?token=<api_key>
    - Header: X-Agent-Token: <api_key>

    Request Body (JSON):
        {
            "type": "notification",
            "useLLM": true/false,
            "title": "...",
            "content": "..."
        }

    Path Parameters:
    - agent_id: Agent UUID

    Query Parameters:
    - token: Optional API key for authentication

    Headers:
    - X-Agent-Token: Optional API key for authentication

    Returns:
        - 200 OK: Notification delivered successfully (WebSocket or MQTT)
        - 202 Accepted: Notification queued (device offline, waiting for reconnect)
        - 400 Bad Request: Invalid payload format (type != "notification")
        - 401 Unauthorized: Invalid or missing authentication token
        - 404 Not Found: Agent or device not found
        - 422 Unprocessable Entity: Schema validation failed (title/content invalid)

    Examples:
        Valid request:
        ```
        POST /agents/550e8400-e29b-41d4-a716-446655440000/webhook?token=secret123
        {
            "type": "notification",
            "useLLM": true,
            "title": "Alert from External System",
            "content": "This is a test notification."
        }
        ```

        Response (device online, delivered via WebSocket):
        ```json
        {
            "success": true,
            "data": {
                "delivered": true,
                "method": "WS"
            }
        }
        ```

        Response (device offline, queued for MQTT):
        ```json
        {
            "success": true,
            "data": {
                "delivered": true,
                "method": "MQTT"
            }
        }
        ```
    """
    try:
        # Get API key from request (query param or header)
        api_key = token or x_agent_token

        if not api_key:
            logger.warning(
                f"Webhook request without authentication for agent {agent_id}"
            )
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Fetch agent with api_key using CRUD
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            schema_to_select=AgentWebhookRead,
            return_as_model=True,
        )

        if not agent:
            logger.warning(f"Webhook request for non-existent agent {agent_id}")
            raise HTTPException(status_code=404, detail="Agent not found")

        # Validate that API key is configured
        if not agent.api_key:
            logger.warning(f"Webhook request for agent without API key: {agent_id}")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Validate API key matches
        if agent.api_key != api_key:
            logger.warning(f"Webhook request with invalid token for agent {agent_id}")
            raise HTTPException(status_code=401, detail="Unauthorized")

        logger.info(f"Webhook authenticated successfully for agent {agent_id}")

        # Check if device is bound to agent
        if not agent.device_id or not agent.device_mac_address:
            logger.warning(f"Webhook request for agent {agent_id} without bound device")
            raise HTTPException(
                status_code=404,
                detail="Agent does not have a bound device",
            )

        # Parse and validate notification payload
        try:
            payload_data = await request.json()
            notification = WebhookNotificationPayload(**payload_data)
        except ValueError as e:
            logger.warning(
                f"Invalid payload format in webhook for agent {agent_id}: {str(e)}"
            )
            raise HTTPException(status_code=400, detail="Invalid payload format")
        except Exception as e:
            logger.warning(f"Schema validation failed for webhook {agent_id}: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Schema validation failed: {str(e)}",
            )

        # Convert Pydantic model to dict for delivery
        payload_dict = notification.model_dump()

        # Get MQTT service from app state if available
        mqtt_service = None
        if hasattr(request.app, "state") and hasattr(request.app.state, "mqtt_service"):
            mqtt_service = request.app.state.mqtt_service

        # Push notification using agent service
        result = await agent_service.push_agent_notification(
            db=db,
            agent_id=agent_id,
            device_id=agent.device_id,
            mac_address=agent.device_mac_address,
            payload=payload_dict,
            mqtt_service=mqtt_service,
            app_state=request.app.state if hasattr(request, "app") else None,
        )

        # Determine response status code
        status_code = 200 if result["delivered"] else 202

        logger.info(
            f"Webhook notification processing complete for agent {agent_id}: "
            f"delivered={result['delivered']}, method={result.get('method')}"
        )

        return SuccessResponse(
            success=True,
            message="Notification processed successfully",
            data=result,
        ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in webhook handler for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
