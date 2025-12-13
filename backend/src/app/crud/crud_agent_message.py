"""
CRUD operations for AgentMessage model.

Methods:
- create_message: Create a new chat message
- get_messages_by_agent: Get paginated messages for an agent
- get_messages_by_session: Get all messages for a specific session
- get_sessions_by_agent: Get distinct sessions with summary
- delete_by_agent: Delete all messages for an agent
- delete_by_session: Delete all messages for a session
"""

from datetime import datetime

from fastcrud import FastCRUD
from sqlalchemy import select, func, delete, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.agent_message import AgentMessage
from ..schemas.agent_message import (
    AgentMessageCreate,
    AgentMessageRead,
    SessionSummary,
)


logger = get_logger(__name__)


class CRUDAgentMessage(
    FastCRUD[AgentMessage, AgentMessageCreate, None, None, None, AgentMessageRead]
):

    async def create_message(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
        chat_type: int,
        content: str,
    ) -> AgentMessageRead:
        """Create a new chat message."""
        try:
            message_data = AgentMessageCreate(
                agent_id=agent_id,
                session_id=session_id,
                chat_type=chat_type,
                content=content,
            )

            message = await self.create(
                db=db,
                object=message_data,
                return_as_model=True,
                schema_to_select=AgentMessageRead,
            )

            logger.debug(f"Created message for agent {agent_id}, session {session_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to create message: {str(e)}")
            raise

    async def get_messages_by_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """Get paginated messages for an agent, ordered by created_at DESC."""
        try:
            result = await self.get_multi(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
                schema_to_select=AgentMessageRead,
                sort_columns=["created_at"],
                sort_orders=["desc"],
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get messages for agent {agent_id}: {str(e)}")
            raise

    async def get_messages_by_session(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """Get messages for a specific session, ordered by created_at DESC (newest first)."""
        try:
            result = await self.get_multi(
                db=db,
                agent_id=agent_id,
                session_id=session_id,
                offset=offset,
                limit=limit,
                schema_to_select=AgentMessageRead,
                sort_columns=["created_at"],
                sort_orders=["desc"],
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {str(e)}")
            raise

    async def get_sessions_by_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """Get distinct sessions with summary for an agent."""
        try:
            # Subquery for session summaries
            stmt = (
                select(
                    AgentMessage.session_id,
                    func.min(AgentMessage.created_at).label("first_message_at"),
                    func.max(AgentMessage.created_at).label("last_message_at"),
                    func.count(AgentMessage.id).label("message_count"),
                )
                .where(AgentMessage.agent_id == agent_id)
                .group_by(AgentMessage.session_id)
                .order_by(func.max(AgentMessage.created_at).desc())
                .offset(offset)
                .limit(limit)
            )

            result = await db.execute(stmt)
            rows = result.all()

            # Count total sessions
            count_stmt = select(func.count(distinct(AgentMessage.session_id))).where(
                AgentMessage.agent_id == agent_id
            )
            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar() or 0

            sessions = [
                SessionSummary(
                    session_id=row.session_id,
                    first_message_at=row.first_message_at,
                    last_message_at=row.last_message_at,
                    message_count=row.message_count,
                )
                for row in rows
            ]

            return {
                "data": sessions,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(f"Failed to get sessions for agent {agent_id}: {str(e)}")
            raise

    async def delete_by_agent(
        self,
        db: AsyncSession,
        agent_id: str,
    ) -> int:
        """Delete all messages for an agent. Returns deleted count."""
        try:
            # Count before delete
            count_stmt = select(func.count(AgentMessage.id)).where(
                AgentMessage.agent_id == agent_id
            )
            count_result = await db.execute(count_stmt)
            count = count_result.scalar() or 0

            # Delete
            stmt = delete(AgentMessage).where(AgentMessage.agent_id == agent_id)
            await db.execute(stmt)
            await db.commit()

            logger.info(f"Deleted {count} messages for agent {agent_id}")
            return count

        except Exception as e:
            logger.error(f"Failed to delete messages for agent {agent_id}: {str(e)}")
            await db.rollback()
            raise

    async def delete_by_session(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
    ) -> int:
        """Delete all messages for a session. Returns deleted count."""
        try:
            # Count before delete
            count_stmt = select(func.count(AgentMessage.id)).where(
                AgentMessage.agent_id == agent_id,
                AgentMessage.session_id == session_id,
            )
            count_result = await db.execute(count_stmt)
            count = count_result.scalar() or 0

            # Delete
            stmt = delete(AgentMessage).where(
                AgentMessage.agent_id == agent_id,
                AgentMessage.session_id == session_id,
            )
            await db.execute(stmt)
            await db.commit()

            logger.info(f"Deleted {count} messages for session {session_id}")
            return count

        except Exception as e:
            logger.error(
                f"Failed to delete messages for session {session_id}: {str(e)}"
            )
            await db.rollback()
            raise


crud_agent_message = CRUDAgentMessage(AgentMessage)
