"""
CRUD operations for AgentTemplate model using FastCRUD pattern.

Methods:
- get_available_for_agent: Get templates for agent (with optional exclude and filtering)
- get_with_validation: Get template with ownership verification
"""

from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.agent_template import AgentTemplate
from ..schemas.agent_template import (
    AgentTemplateCreate,
    AgentTemplateDelete,
    AgentTemplateRead,
    AgentTemplateUpdate,
    AgentTemplateUpdateInternal,
)

logger = get_logger(__name__)


class CRUDAgentTemplate(
    FastCRUD[
        AgentTemplate,
        AgentTemplateCreate,
        AgentTemplateUpdate,
        AgentTemplateUpdateInternal,
        AgentTemplateDelete,
        AgentTemplateRead,
    ]
):
    """CRUD operations for AgentTemplate model with custom methods."""

    async def get_available_for_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 10,
        exclude_id: str | None = None,
    ) -> dict:
        """
        Get templates for agent with optional exclusion and filtering.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            user_id: User UUID (ownership filter)
            offset: List offset
            limit: List limit
            exclude_id: Template ID to exclude (optional)

        Returns:
            dict: {data: [...], total_count: int}
        """
        try:
            logger.debug(
                f"Fetching available templates for agent {agent_id}, "
                f"offset={offset}, limit={limit}, exclude_id={exclude_id}"
            )

            # Build filters
            filters = {
                "agent_id": agent_id,
                "user_id": user_id,
                "is_deleted": False,
            }

            # Get templates using get_multi
            result = await self.get_multi(
                db=db,
                offset=offset,
                limit=limit,
                schema_to_select=AgentTemplateRead,
                return_as_model=True,
                return_total_count=True,
                **filters,
            )

            templates = result.get("data", [])
            total_count = result.get("total_count", 0)

            # Filter out excluded template if provided
            if exclude_id:
                templates = [t for t in templates if str(t.id) != str(exclude_id)]
                total_count = len(templates)  # Adjust count after filtering

            logger.info(
                f"Successfully fetched {len(templates)} available templates "
                f"for agent {agent_id}"
            )

            return {
                "data": templates,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(
                f"Failed to get available templates for agent {agent_id}: {str(e)}"
            )
            raise

    async def get_with_validation(
        self,
        db: AsyncSession,
        template_id: str,
        user_id: str,
    ) -> AgentTemplateRead | None:
        """
        Get template with ownership validation.

        Args:
            db: AsyncSession
            template_id: Template UUID
            user_id: User UUID (ownership filter)

        Returns:
            AgentTemplateRead if owned, None otherwise
        """
        try:
            logger.debug(f"Validating template {template_id} for user {user_id}")

            template = await self.get(
                db=db,
                id=template_id,
                user_id=user_id,
                schema_to_select=AgentTemplateRead,
                return_as_model=True,
            )

            if template:
                logger.debug(f"Template {template_id} validated for user {user_id}")
            else:
                logger.warning(f"Template {template_id} not owned by user {user_id}")

            return template

        except Exception as e:
            logger.error(f"Failed to validate template {template_id}: {str(e)}")
            return None


crud_agent_template = CRUDAgentTemplate(AgentTemplate)
