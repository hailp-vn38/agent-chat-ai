"""
CRUD operations for AgentTemplateAssignment model.

Manages the many-to-many relationship between agents and templates.

Methods:
- assign_template_to_agent: Assign a template to an agent
- unassign_template_from_agent: Remove template assignment
- get_assignments_for_agent: Get all templates assigned to agent
- set_active_template: Set a template as active for agent
- get_active_template: Get the active template for agent
"""

from datetime import datetime, timezone

from fastcrud import FastCRUD
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.agent_template_assignment import AgentTemplateAssignment
from ..schemas.agent_template_assignment import (
    AssignmentCreate,
    AssignmentRead,
)

logger = get_logger(__name__)


class CRUDAgentTemplateAssignment(
    FastCRUD[
        AgentTemplateAssignment,
        AssignmentCreate,
        AssignmentRead,
        AssignmentRead,
        AssignmentRead,
        AssignmentRead,
    ]
):
    """CRUD operations for AgentTemplateAssignment model."""

    async def assign_template_to_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
        set_active: bool = False,
    ) -> AssignmentRead:
        """
        Assign a template to an agent.

        If the assignment already exists, returns existing.
        If set_active=True, deactivates other templates first.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            template_id: Template UUID
            set_active: Whether to set this as active template

        Returns:
            AssignmentRead: Created or existing assignment
        """
        try:
            logger.debug(
                f"Assigning template {template_id} to agent {agent_id}, "
                f"set_active={set_active}"
            )

            # Check if assignment already exists
            existing = await self.get(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            if existing:
                logger.debug(
                    f"Assignment already exists for agent {agent_id} "
                    f"and template {template_id}"
                )
                if set_active and not existing.get("is_active"):
                    # Activate this template
                    await self.set_active_template(db, agent_id, template_id)
                    existing["is_active"] = True
                return AssignmentRead(**existing)

            # Deactivate other templates if setting active
            if set_active:
                await self._deactivate_all_for_agent(db, agent_id)

            # Create new assignment
            assignment = AssignmentCreate(
                agent_id=agent_id,
                template_id=template_id,
                is_active=set_active,
            )

            created = await self.create(
                db=db,
                object=assignment,
                schema_to_select=AssignmentRead,
                return_as_model=True,
            )

            logger.info(f"Template {template_id} assigned to agent {agent_id}")
            return created

        except Exception as e:
            logger.error(
                f"Failed to assign template {template_id} to agent {agent_id}: {str(e)}"
            )
            raise

    async def unassign_template_from_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
    ) -> bool:
        """
        Remove template assignment from agent.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            template_id: Template UUID

        Returns:
            bool: True if assignment was removed, False if not found
        """
        try:
            logger.debug(f"Unassigning template {template_id} from agent {agent_id}")

            # Check if assignment exists
            existing = await self.get(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            if not existing:
                logger.warning(
                    f"Assignment not found for agent {agent_id} "
                    f"and template {template_id}"
                )
                return False

            # Delete assignment
            await self.db_delete(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            logger.info(f"Template {template_id} unassigned from agent {agent_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to unassign template {template_id} from agent {agent_id}: {str(e)}"
            )
            raise

    async def get_assignments_for_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """
        Get all templates assigned to an agent.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            offset: List offset
            limit: List limit

        Returns:
            dict: {data: [...], total_count: int}
        """
        try:
            logger.debug(f"Fetching assignments for agent {agent_id}")

            result = await self.get_multi(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
                schema_to_select=AssignmentRead,
                return_as_model=True,
                return_total_count=True,
            )

            logger.debug(
                f"Found {len(result.get('data', []))} assignments for agent {agent_id}"
            )

            return {
                "data": result.get("data", []),
                "total_count": result.get("total_count", 0),
            }

        except Exception as e:
            logger.error(f"Failed to get assignments for agent {agent_id}: {str(e)}")
            raise

    async def set_active_template(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
    ) -> bool:
        """
        Set a template as active for an agent.

        Deactivates all other templates first, then activates the specified one.

        Args:
            db: AsyncSession
            agent_id: Agent UUID
            template_id: Template UUID

        Returns:
            bool: True if successful
        """
        try:
            logger.debug(
                f"Setting template {template_id} as active for agent {agent_id}"
            )

            # Check assignment exists
            assignment = await self.get(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            if not assignment:
                logger.warning(
                    f"Assignment not found for agent {agent_id} "
                    f"and template {template_id}"
                )
                return False

            # Deactivate all templates for this agent
            await self._deactivate_all_for_agent(db, agent_id)

            # Activate the specified template
            stmt = (
                update(AgentTemplateAssignment)
                .where(
                    AgentTemplateAssignment.agent_id == agent_id,
                    AgentTemplateAssignment.template_id == template_id,
                )
                .values(is_active=True)
            )
            await db.execute(stmt)
            await db.commit()

            logger.info(f"Template {template_id} set as active for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to set active template for agent {agent_id}: {str(e)}"
            )
            raise

    async def get_active_template(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> AssignmentRead | None:
        """
        Get the active template assignment for an agent.

        Args:
            db: AsyncSession
            agent_id: Agent UUID

        Returns:
            AssignmentRead if found, None otherwise
        """
        try:
            assignment = await self.get(
                db=db,
                agent_id=agent_id,
                is_active=True,
                schema_to_select=AssignmentRead,
                return_as_model=True,
            )
            return assignment

        except Exception as e:
            logger.error(
                f"Failed to get active template for agent {agent_id}: {str(e)}"
            )
            return None

    async def _deactivate_all_for_agent(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> None:
        """Deactivate all template assignments for an agent."""
        stmt = (
            update(AgentTemplateAssignment)
            .where(AgentTemplateAssignment.agent_id == agent_id)
            .values(is_active=False)
        )
        await db.execute(stmt)
        await db.commit()
        logger.debug(f"Deactivated all templates for agent {agent_id}")


crud_assignment = CRUDAgentTemplateAssignment(AgentTemplateAssignment)
