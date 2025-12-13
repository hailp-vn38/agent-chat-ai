"""
Scheduler service for periodic background tasks.
Handles scheduling of cleanup jobs and other periodic operations.
"""

import asyncio
import logging
from datetime import time
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..core.logger import get_logger
from ..core.worker.functions import cleanup_expired_deleted_users

logger = get_logger(__name__)

# Suppress verbose APScheduler logs
logging.getLogger("apscheduler").setLevel(logging.WARNING)


class SchedulerService:
    """Service for managing scheduled background tasks."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._is_running = False

    async def start(self) -> None:
        """Start the scheduler and register jobs."""
        if self._is_running:
            logger.warning("Scheduler đã chạy rồi")
            return

        try:
            self.scheduler = AsyncIOScheduler()

            # Schedule cleanup job to run daily at 3:00 AM
            self.scheduler.add_job(
                self._run_cleanup_job,
                trigger=CronTrigger(hour=3, minute=0),
                id="cleanup_expired_deleted_users",
                name="Cleanup Expired Deleted Users",
                replace_existing=True,
                max_instances=1,  # Prevent concurrent runs
            )

            self.scheduler.start()
            self._is_running = True
            logger.info("Cleanup scheduler đã khởi động (chạy lúc 3:00 AM hàng ngày)")

        except Exception as e:
            logger.error(f"Không thể khởi động scheduler: {str(e)}")
            raise

    async def _run_cleanup_job(self) -> None:
        """Wrapper to run cleanup job with proper error handling."""
        try:
            logger.info("Bắt đầu cleanup expired user accounts")

            # Create a mock context object for ARQ compatibility
            class MockContext:
                pass

            ctx = MockContext()
            result = await cleanup_expired_deleted_users(ctx)
            logger.info(f"Cleanup job hoàn thành: {result}")

        except Exception as e:
            logger.error(f"Cleanup job thất bại: {str(e)}")

    async def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        if not self._is_running:
            logger.warning("Scheduler chưa được khởi động")
            return

        try:
            if self.scheduler:
                self.scheduler.shutdown(wait=True)
                self._is_running = False
                logger.info("Scheduler đã shutdown")
        except Exception as e:
            logger.error(f"Lỗi khi shutdown scheduler: {str(e)}")

    async def run_cleanup_now(self) -> str:
        """Manually trigger cleanup job immediately (for testing/admin)."""
        try:
            logger.info("Thực thi cleanup job thủ công")

            class MockContext:
                pass

            ctx = MockContext()
            result = await cleanup_expired_deleted_users(ctx)
            logger.info(f"Cleanup thủ công hoàn thành: {result}")
            return result

        except Exception as e:
            error_msg = f"Cleanup thủ công thất bại: {str(e)}"
            logger.error(error_msg)
            raise


# Global scheduler instance
scheduler_service = SchedulerService()
