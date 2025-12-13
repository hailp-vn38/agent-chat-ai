"""
CRUD operations for Template model using FastCRUD pattern.

Methods:
- get_templates_for_user: Get templates owned by user
- get_agents_using_template: List agents assigned to a template
- get_with_validation: Get template with ownership verification
- can_access_template: Check if user can access template (owner or public)
"""

from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.template import Template
from ..schemas.template import (
    TemplateCreate,
    TemplateDelete,
    TemplateRead,
    TemplateUpdate,
    TemplateUpdateInternal,
)

logger = get_logger(__name__)


class CRUDTemplate(
    FastCRUD[
        Template,
        TemplateCreate,
        TemplateUpdate,
        TemplateUpdateInternal,
        TemplateDelete,
        TemplateRead,
    ]
):
    """CRUD operations for Template model with custom methods."""

    async def get_templates_for_user(
        self,
        db: AsyncSession,
        user_id: str,
        offset: int = 0,
        limit: int = 10,
        include_public: bool = False,
    ) -> dict:
        """
        Get templates for user (owned or public).

        Args:
            db: AsyncSession
            user_id: User UUID
            offset: List offset
            limit: List limit
            include_public: Include public templates from other users

        Returns:
            dict: {data: [...], total_count: int}
        """
        try:
            logger.debug(
                f"Fetching templates for user {user_id}, "
                f"offset={offset}, limit={limit}, include_public={include_public}"
            )

            if include_public:
                # Get user's templates OR public templates
                # This requires custom query logic
                from sqlalchemy import or_, select, func
                from ..models.template import Template

                stmt = (
                    select(Template)
                    .where(
                        Template.is_deleted == False,
                        or_(
                            Template.user_id == user_id,
                            Template.is_public == True,
                        ),
                    )
                    .offset(offset)
                    .limit(limit)
                )

                count_stmt = select(func.count()).where(
                    Template.is_deleted == False,
                    or_(
                        Template.user_id == user_id,
                        Template.is_public == True,
                    ),
                )

                result = await db.execute(stmt)
                templates = result.scalars().all()

                count_result = await db.execute(count_stmt)
                total_count = count_result.scalar() or 0

                templates_data = [
                    TemplateRead.model_validate(t, from_attributes=True)
                    for t in templates
                ]

                return {
                    "data": templates_data,
                    "total_count": total_count,
                }
            else:
                # Only user's templates
                result = await self.get_multi(
                    db=db,
                    offset=offset,
                    limit=limit,
                    user_id=user_id,
                    is_deleted=False,
                    schema_to_select=TemplateRead,
                    return_as_model=True,
                    return_total_count=True,
                )

                return {
                    "data": result.get("data", []),
                    "total_count": result.get("total_count", 0),
                }

        except Exception as e:
            logger.error(f"Failed to get templates for user {user_id}: {str(e)}")
            raise

    async def get_agents_using_template(
        self,
        db: AsyncSession,
        template_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """
        Get agents that have this template assigned.

        Args:
            db: AsyncSession
            template_id: Template UUID
            user_id: User UUID (for authorization)
            offset: List offset
            limit: List limit

        Returns:
            dict: {data: [...], total_count: int}
        """
        try:
            from sqlalchemy import select, func
            from ..models.agent import Agent
            from ..models.agent_template_assignment import AgentTemplateAssignment
            from ..schemas.agent import AgentRead

            logger.debug(f"Fetching agents using template {template_id}")

            # First verify user can access this template
            template = await self.get(db=db, id=template_id, is_deleted=False)
            if not template:
                return {"data": [], "total_count": 0}

            # Check access: owner or public
            if template.get("user_id") != user_id and not template.get("is_public"):
                logger.warning(f"User {user_id} cannot access template {template_id}")
                return {"data": [], "total_count": 0}

            # Query agents via assignment table
            stmt = (
                select(Agent)
                .join(
                    AgentTemplateAssignment,
                    Agent.id == AgentTemplateAssignment.agent_id,
                )
                .where(
                    AgentTemplateAssignment.template_id == template_id,
                    Agent.is_deleted == False,
                    Agent.user_id == user_id,  # Only show user's own agents
                )
                .offset(offset)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(Agent)
                .join(
                    AgentTemplateAssignment,
                    Agent.id == AgentTemplateAssignment.agent_id,
                )
                .where(
                    AgentTemplateAssignment.template_id == template_id,
                    Agent.is_deleted == False,
                    Agent.user_id == user_id,
                )
            )

            result = await db.execute(stmt)
            agents = result.scalars().all()

            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar() or 0

            agents_data = [
                AgentRead.model_validate(a, from_attributes=True) for a in agents
            ]

            logger.info(f"Found {len(agents_data)} agents using template {template_id}")

            return {
                "data": agents_data,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(f"Failed to get agents using template {template_id}: {str(e)}")
            raise

    async def get_with_validation(
        self,
        db: AsyncSession,
        template_id: str,
        user_id: str,
    ) -> TemplateRead | None:
        """
        Get template with ownership validation.

        Args:
            db: AsyncSession
            template_id: Template UUID
            user_id: User UUID (ownership filter)

        Returns:
            TemplateRead if owned, None otherwise
        """
        try:
            logger.debug(f"Validating template {template_id} for user {user_id}")

            template = await self.get(
                db=db,
                id=template_id,
                user_id=user_id,
                is_deleted=False,
                schema_to_select=TemplateRead,
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

    async def can_access_template(
        self,
        db: AsyncSession,
        template_id: str,
        user_id: str,
    ) -> bool:
        """
        Check if user can access template (owner or public).

        Args:
            db: AsyncSession
            template_id: Template UUID
            user_id: User UUID

        Returns:
            bool: True if user can access
        """
        try:
            template = await self.get(db=db, id=template_id, is_deleted=False)
            if not template:
                return False

            # Owner always has access
            if template.get("user_id") == user_id:
                return True

            # Public templates readable by all
            if template.get("is_public"):
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check template access: {str(e)}")
            return False

    async def can_modify_template(
        self,
        db: AsyncSession,
        template_id: str,
        user_id: str,
    ) -> bool:
        """
        Check if user can modify template (owner only).

        Args:
            db: AsyncSession
            template_id: Template UUID
            user_id: User UUID

        Returns:
            bool: True if user can modify
        """
        try:
            template = await self.get(
                db=db,
                id=template_id,
                user_id=user_id,
                is_deleted=False,
            )
            return template is not None

        except Exception as e:
            logger.error(f"Failed to check template modify access: {str(e)}")
            return False


crud_template = CRUDTemplate(Template)
