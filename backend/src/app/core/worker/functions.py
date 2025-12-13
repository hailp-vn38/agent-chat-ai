import asyncio
import logging
from datetime import datetime, timedelta

import uvloop
from arq.worker import Worker
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db.database import async_get_db
from ...models.user import User

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# -------- background tasks --------
async def sample_background_task(ctx: Worker, name: str) -> str:
    await asyncio.sleep(5)
    return f"Task {name} is complete!"


async def cleanup_expired_deleted_users(ctx: Worker) -> str:
    """
    Hard delete users that have been soft-deleted for more than 30 days.
    Runs daily to cleanup expired deleted accounts.
    """
    logger.info("Starting cleanup job for expired deleted users")

    try:
        # Calculate cutoff date (30 days ago)
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Get database session
        async for db in async_get_db():
            try:
                # Query users deleted more than 30 days ago
                stmt = select(User).where(
                    User.is_deleted == True,
                    User.deleted_at.isnot(None),
                    User.deleted_at < cutoff_date,
                )
                result = await db.execute(stmt)
                expired_users = result.scalars().all()

                if not expired_users:
                    logger.info("No expired deleted users found for cleanup")
                    return "No users to cleanup"

                # Get user IDs for logging
                user_ids = [str(user.id) for user in expired_users]
                logger.info(
                    f"Found {len(expired_users)} expired deleted users: {user_ids}"
                )

                # Hard delete users
                delete_stmt = delete(User).where(
                    User.is_deleted == True,
                    User.deleted_at.isnot(None),
                    User.deleted_at < cutoff_date,
                )
                result = await db.execute(delete_stmt)
                await db.commit()

                deleted_count = result.rowcount
                logger.info(
                    f"Successfully deleted {deleted_count} expired user accounts"
                )

                return f"Deleted {deleted_count} expired user accounts"

            except Exception as e:
                await db.rollback()
                logger.error(f"Error during cleanup: {str(e)}")
                raise
            finally:
                await db.close()

    except Exception as e:
        error_msg = f"Cleanup job failed: {str(e)}"
        logger.error(error_msg)
        return error_msg


# -------- base functions --------
async def startup(ctx: Worker) -> None:
    logging.info("Worker Started")


async def shutdown(ctx: Worker) -> None:
    logging.info("Worker end")
