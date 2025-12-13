"""Template API router.

Exposes endpoints to list/create/update/delete templates, manage template assignments
to agents, and list agents using a template.

Templates are now independent resources that can be shared across multiple agents.
"""

from datetime import datetime, timezone as dt_timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.base import PaginatedResponse, SuccessResponse

from ...api.dependencies import get_current_user
from ...core.db.database import async_get_db
from ...core.exceptions.http_exceptions import (
    ForbiddenException,
    NotFoundException,
)
from ...core.logger import get_logger
from ...crud.crud_template import crud_template
from ...crud.crud_agent_template_assignment import crud_assignment
from ...crud.crud_agent import crud_agent
from ...crud.crud_provider import crud_provider
from ...schemas.template import (
    TemplateCreate,
    TemplateCreateInternal,
    TemplateRead,
    TemplateUpdate,
    TemplateUpdateInternal,
    TemplateWithProvidersRead,
    ProviderInfo,
)
from ...schemas.agent import AgentRead
from ...schemas.agent_template_assignment import AssignmentRead
from ...ai.module_factory import parse_provider_reference
from ...config import load_config

logger = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


# ========== Helper Functions ==========


# Provider categories mapping for validation
PROVIDER_CATEGORIES = {
    "ASR": "ASR",
    "LLM": "LLM",
    "VLLM": "VLLM",
    "TTS": "TTS",
    "Memory": "Memory",
    "Intent": "Intent",
}


async def validate_provider_references(
    db: AsyncSession,
    user_id: str,
    provider_fields: dict[str, str | None],
) -> list[str]:
    """
    Validate provider references (config:{name} or db:{uuid} format).

    Args:
        db: AsyncSession
        user_id: UUID of user
        provider_fields: Dict of {field_name: provider_reference} to validate

    Returns:
        list[str]: List of validation errors (empty if all valid)
    """
    errors = []
    config = None  # Lazy load

    for field_name, reference in provider_fields.items():
        if reference is None:
            continue

        parsed = parse_provider_reference(reference)
        if parsed is None:
            errors.append(
                f"Invalid provider reference format for {field_name}: {reference}"
            )
            continue

        source, value = parsed
        expected_category = PROVIDER_CATEGORIES.get(field_name)

        if source == "config":
            # Validate config provider exists
            if config is None:
                try:
                    config = load_config()
                except Exception as e:
                    errors.append(f"Failed to load config: {str(e)}")
                    continue

            if expected_category not in config:
                errors.append(f"Category '{expected_category}' not found in config")
            elif value not in config[expected_category]:
                errors.append(
                    f"Provider '{value}' not found in config.yml for {field_name}"
                )

        elif source == "db":
            # Validate db provider exists and belongs to user
            provider = await crud_provider.get(
                db=db,
                id=value,
                user_id=user_id,
                is_deleted=False,
            )

            if not provider:
                errors.append(
                    f"Provider '{value}' for {field_name} not found or not owned by user"
                )
                continue

            # Validate provider category matches field
            if expected_category and provider.get("category") != expected_category:
                errors.append(
                    f"Provider '{value}' has category '{provider.get('category')}' "
                    f"but {field_name} requires '{expected_category}'"
                )

    return errors


async def _enrich_template_with_providers(
    db: AsyncSession,
    template: TemplateRead | dict,
) -> dict:
    """
    Enrich a single template with full provider info.

    Args:
        db: AsyncSession
        template: TemplateRead model or dict

    Returns:
        dict: Template with provider info instead of just references
    """
    provider_fields = ["ASR", "LLM", "VLLM", "TTS", "Memory", "Intent"]
    config = None

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

        if source == "db":
            provider = await crud_provider.get(db=db, id=value, is_deleted=False)
            if provider:
                template_dict[field] = ProviderInfo(
                    reference=f"db:{provider.get('id')}",
                    id=provider.get("id"),
                    name=provider.get("name"),
                    type=provider.get("type"),
                    source="user",
                )
            else:
                template_dict[field] = None
        elif source == "config":
            if config is None:
                try:
                    config = load_config()
                except Exception:
                    config = {}

            category = PROVIDER_CATEGORIES.get(field, field)
            if category in config and value in config[category]:
                cfg = config[category][value]
                provider_type = (
                    cfg.get("type", value) if isinstance(cfg, dict) else value
                )
                template_dict[field] = ProviderInfo(
                    reference=f"config:{value}",
                    name=value,
                    type=provider_type,
                    source="default",
                )
            else:
                template_dict[field] = None

    return template_dict


async def _enrich_templates_with_providers(
    db: AsyncSession,
    templates: list,
) -> list[dict]:
    """
    Enrich multiple templates with full provider info.

    Args:
        db: AsyncSession
        templates: List of TemplateRead models or dicts

    Returns:
        list[dict]: Templates with provider info
    """
    if not templates:
        return []

    enriched = []
    for template in templates:
        enriched_template = await _enrich_template_with_providers(db, template)
        enriched.append(enriched_template)

    return enriched


# ========== Template CRUD Endpoints ==========


@router.get("", response_model=PaginatedResponse[TemplateWithProvidersRead])
async def list_templates(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    include_public: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """
    Return a paginated list of templates owned by the current user.

    Optionally include public templates from other users.

    Query Parameters:
    - page: int (1-based, default=1)
    - page_size: int (1-100, default=10)
    - include_public: bool (default=False) - Include public templates

    Returns:
        PaginatedResponse[TemplateWithProvidersRead]: Structured pagination payload
    """
    try:
        logger.debug(
            f"Listing templates for user {current_user['id']}, "
            f"include_public={include_public}"
        )

        templates_data = await crud_template.get_templates_for_user(
            db=db,
            user_id=current_user["id"],
            offset=(page - 1) * page_size,
            limit=page_size,
            include_public=include_public,
        )

        total = templates_data.get("total_count", 0)
        total_pages = (total + page_size - 1) // page_size

        # Enrich templates with provider info
        enriched_templates = await _enrich_templates_with_providers(
            db, templates_data["data"]
        )

        return PaginatedResponse(
            success=True,
            message="Success",
            data=enriched_templates,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=TemplateWithProvidersRead, status_code=201)
async def create_template(
    template: TemplateCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """
    Create a new template for the authenticated user.

    Templates are independent and can be assigned to multiple agents.

    Body:
        TemplateCreate: Template content with provider references

    Returns:
        TemplateWithProvidersRead: Newly created template with provider info
    """
    try:
        logger.info(
            f"Creating template '{template.name}' for user {current_user['id']}"
        )

        # Validate provider references
        provider_fields = {
            "ASR": template.ASR,
            "LLM": template.LLM,
            "VLLM": template.VLLM,
            "TTS": template.TTS,
            "Memory": template.Memory,
            "Intent": template.Intent,
        }
        validation_errors = await validate_provider_references(
            db=db,
            user_id=current_user["id"],
            provider_fields=provider_fields,
        )
        if validation_errors:
            raise HTTPException(status_code=400, detail="; ".join(validation_errors))

        # Create template
        template_create_internal = TemplateCreateInternal(
            **template.model_dump(),
            user_id=current_user["id"],
        )

        created_template = await crud_template.create(
            db=db,
            object=template_create_internal,
            schema_to_select=TemplateRead,
            return_as_model=True,
        )

        logger.info(f"Template {created_template.id} created successfully")

        # Enrich with provider info
        enriched = await _enrich_template_with_providers(db, created_template)
        return enriched

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{template_id}", response_model=TemplateWithProvidersRead)
async def get_template(
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """
    Get template details by ID.

    User can access templates they own or public templates.

    Returns:
        TemplateWithProvidersRead: Template with provider info

    Raises:
        NotFoundException: If template not found
        ForbiddenException: If user cannot access template
    """
    try:
        logger.debug(f"Fetching template {template_id}")

        template = await crud_template.get(
            db=db,
            id=template_id,
            is_deleted=False,
            schema_to_select=TemplateRead,
            return_as_model=True,
        )

        if not template:
            raise NotFoundException(f"Template {template_id} not found")

        # Check access
        can_access = await crud_template.can_access_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
        )

        if not can_access:
            raise ForbiddenException("You do not have access to this template")

        # Enrich with provider info
        enriched = await _enrich_template_with_providers(db, template)
        return enriched

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{template_id}", response_model=TemplateWithProvidersRead)
async def update_template(
    template_id: str,
    template_update: TemplateUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """
    Update a template.

    Only the owner can update a template.

    Body:
        TemplateUpdate: Partial template payload

    Returns:
        TemplateWithProvidersRead: Updated template with provider info

    Raises:
        NotFoundException: If template not found
        ForbiddenException: If user is not the owner
    """
    try:
        logger.debug(f"Updating template {template_id}")

        # Check ownership
        can_modify = await crud_template.can_modify_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
        )

        if not can_modify:
            # Check if template exists
            template = await crud_template.get(db=db, id=template_id, is_deleted=False)
            if not template:
                raise NotFoundException(f"Template {template_id} not found")
            raise ForbiddenException("You can only modify templates you own")

        # Validate provider references if any are being updated
        update_dict = template_update.model_dump(exclude_unset=True)
        provider_fields = {
            field: update_dict.get(field)
            for field in ["ASR", "LLM", "VLLM", "TTS", "Memory", "Intent"]
            if field in update_dict
        }
        if provider_fields:
            validation_errors = await validate_provider_references(
                db=db,
                user_id=current_user["id"],
                provider_fields=provider_fields,
            )
            if validation_errors:
                raise HTTPException(
                    status_code=400, detail="; ".join(validation_errors)
                )

        # Update template
        update_data = TemplateUpdateInternal(
            **update_dict,
            updated_at=datetime.now(dt_timezone.utc),
        )

        updated_template = await crud_template.update(
            db=db,
            object=update_data,
            id=template_id,
            schema_to_select=TemplateRead,
            return_as_model=True,
        )

        logger.info(f"Template {template_id} updated successfully")

        # Enrich with provider info
        enriched = await _enrich_template_with_providers(db, updated_template)
        return enriched

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """
    Soft delete a template.

    Only the owner can delete a template.
    Deleting a template will also remove all assignments and clear
    active_template_id from agents using it.

    Raises:
        NotFoundException: If template not found
        ForbiddenException: If user is not the owner
    """
    try:
        logger.info(f"Deleting template {template_id}")

        # Check ownership
        can_modify = await crud_template.can_modify_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
        )

        if not can_modify:
            template = await crud_template.get(db=db, id=template_id, is_deleted=False)
            if not template:
                raise NotFoundException(f"Template {template_id} not found")
            raise ForbiddenException("You can only delete templates you own")

        # Get agents using this template to clear their active_template_id
        from sqlalchemy import select, update
        from ...models.agent import Agent

        stmt = (
            update(Agent)
            .where(Agent.active_template_id == template_id)
            .values(active_template_id=None, updated_at=datetime.now(dt_timezone.utc))
        )
        await db.execute(stmt)

        # Soft delete template (cascade will handle assignments)
        await crud_template.delete(db=db, id=template_id)

        logger.info(f"Template {template_id} deleted successfully")

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ========== Template Assignment Endpoints ==========


@router.get("/{template_id}/agents", response_model=PaginatedResponse[AgentRead])
async def list_agents_using_template(
    template_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    """
    List agents that have this template assigned.

    Only shows agents owned by the current user.

    Returns:
        PaginatedResponse[AgentRead]: Paginated list of agents

    Raises:
        NotFoundException: If template not found
        ForbiddenException: If user cannot access template
    """
    try:
        logger.debug(f"Listing agents using template {template_id}")

        # Check access
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

        agents_data = await crud_template.get_agents_using_template(
            db=db,
            template_id=template_id,
            user_id=current_user["id"],
            offset=(page - 1) * page_size,
            limit=page_size,
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

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except Exception as e:
        logger.error(f"Error listing agents using template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/{template_id}/agents/{agent_id}",
    response_model=SuccessResponse[AssignmentRead],
    status_code=201,
)
async def add_agent_to_template(
    template_id: str,
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    set_active: Annotated[bool, Query()] = False,
) -> dict:
    """
    Add an agent to this template (assign template to agent).

    User must own the agent. User must own the template OR template must be public.

    Query Parameters:
    - set_active: bool (default=False) - Set as active template for agent

    Returns:
        SuccessResponse[AssignmentRead]: Created assignment

    Raises:
        NotFoundException: If template or agent not found
        ForbiddenException: If user cannot access template or doesn't own agent
    """
    try:
        logger.info(f"Assigning template {template_id} to agent {agent_id}")

        # Check template access
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

        # Check agent ownership
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            user_id=current_user["id"],
            is_deleted=False,
        )

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Create assignment
        assignment = await crud_assignment.assign_template_to_agent(
            db=db,
            agent_id=agent_id,
            template_id=template_id,
            set_active=set_active,
        )

        # If set_active, update agent's active_template_id
        if set_active:
            from ...schemas.agent import AgentUpdateInternal

            update_data = AgentUpdateInternal(
                active_template_id=template_id,
                updated_at=datetime.now(dt_timezone.utc),
            )
            await crud_agent.update(
                db=db,
                object=update_data,
                id=agent_id,
            )
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
        logger.error(f"Error assigning template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{template_id}/agents/{agent_id}", status_code=204)
async def remove_agent_from_template(
    template_id: str,
    agent_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
) -> None:
    """
    Remove an agent from this template (unassign template from agent).

    User must own the agent.
    If this was the active template, clears agent's active_template_id.

    Raises:
        NotFoundException: If assignment not found
        ForbiddenException: If user doesn't own agent
    """
    try:
        logger.info(f"Unassigning template {template_id} from agent {agent_id}")

        # Check agent ownership
        agent = await crud_agent.get(
            db=db,
            id=agent_id,
            user_id=current_user["id"],
            is_deleted=False,
            schema_to_select=AgentRead,
            return_as_model=True,
        )

        if not agent:
            raise NotFoundException(f"Agent {agent_id} not found")

        # Remove assignment
        removed = await crud_assignment.unassign_template_from_agent(
            db=db,
            agent_id=agent_id,
            template_id=template_id,
        )

        if not removed:
            raise NotFoundException(
                f"Assignment not found for template {template_id} and agent {agent_id}"
            )

        # If this was active template, clear it
        if agent.active_template_id == template_id:
            from ...schemas.agent import AgentUpdateInternal

            update_data = AgentUpdateInternal(
                active_template_id=None,
                updated_at=datetime.now(dt_timezone.utc),
            )
            await crud_agent.update(
                db=db,
                object=update_data,
                id=agent_id,
            )
            logger.info(f"Cleared active template for agent {agent_id}")

        logger.info(f"Template {template_id} unassigned from agent {agent_id}")

    except NotFoundException:
        raise
    except ForbiddenException:
        raise
    except Exception as e:
        logger.error(f"Error unassigning template: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
