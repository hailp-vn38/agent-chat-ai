"""CRUD operations for Reminder model using FastCRUD.

Pattern: FastCRUD generic with type hints for model, create, update, read, delete schemas.
Provides async database operations: create, read, update, delete, list, etc.

Reusable helper methods with comprehensive error handling:
- create_reminder_safe: Create reminder with validation
- get_reminder_by_id: Retrieve single reminder with error handling
- list_reminders_filtered: List with pagination, filtering, and search
- update_reminder_safe: Update reminder with status validation
- soft_delete_reminder: Mark reminder as deleted
- update_status_by_id: Direct status updates (pending/delivered/received/failed)
"""

from datetime import datetime, timezone
from typing import Any

from fastcrud import FastCRUD
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..models.reminder import Reminder, ReminderStatus
from ..schemas.reminder import (
    ReminderCreate,
    ReminderCreateInternal,
    ReminderDelete,
    ReminderListRead,
    ReminderRead,
    ReminderUpdate,
    ReminderUpdateInternal,
)

logger = get_logger(__name__)


class CRUDReminders(
    FastCRUD[
        Reminder,
        ReminderCreateInternal,
        ReminderUpdate,
        ReminderUpdateInternal,
        ReminderDelete,
        ReminderRead,
    ]
):
    """CRUD operations for Reminder model using FastCRUD with full error handling."""

    async def create_reminder_safe(
        self,
        db: AsyncSession,
        reminder_create_internal: ReminderCreateInternal,
    ) -> ReminderRead:
        """
        Create a new reminder safely.

        Args:
            db: AsyncSession for database operations
            reminder_create_internal: ReminderCreateInternal schema with reminder_id

        Returns:
            ReminderRead: Created reminder data

        Raises:
            Exception: If reminder creation fails
        """
        try:
            logger.debug(
                f"Creating reminder with id: {reminder_create_internal.reminder_id}"
            )

            reminder = await self.create(
                db=db,
                object=reminder_create_internal,
                schema_to_select=ReminderRead,
                return_as_model=True,
            )

            logger.debug(f"Reminder {reminder.id} created successfully")
            return reminder

        except Exception as e:
            logger.error(f"Failed to create reminder: {str(e)}")
            raise

    async def create_reminder_from_dto(
        self,
        db: AsyncSession,
        reminder_create: ReminderCreate,
    ) -> ReminderRead:
        """
        Create a new reminder from ReminderCreate DTO.

        Handles all data transformation:
        - Generates reminder_id (UUID hex)
        - Normalizes remind_at timezone (UTC)
        - Creates ReminderCreateInternal
        - Persists to database

        Args:
            db: AsyncSession for database operations
            reminder_create: ReminderCreate schema (from API request)

        Returns:
            ReminderRead: Created reminder data

        Raises:
            ValueError: If data transformation fails
            Exception: If database operation fails
        """
        try:
            import uuid as uuid_module
            import pytz

            logger.debug(f"Creating reminder for agent: {reminder_create.agent_id}")

            # Generate unique reminder_id
            reminder_id = uuid_module.uuid4().hex
            logger.debug(f"Generated reminder_id: {reminder_id}")

            # Get agent with user info to access user's timezone
            from ..crud.crud_agent import crud_agent

            agent = await crud_agent.get(
                db=db,
                id=reminder_create.agent_id,
                schema_to_select=None,
                return_as_model=False,
            )
            if not agent:
                raise ValueError(f"Agent {reminder_create.agent_id} not found")

            # Get user timezone from agent.user_id (join required)
            from ..models.user import User

            user = (
                await db.get(User, agent.user_id) if hasattr(agent, "user_id") else None
            )
            user_timezone_str = user.timezone if user else "UTC"
            logger.debug(f"Using user timezone: {user_timezone_str}")

            # Normalize remind_at to UTC
            remind_at_utc = reminder_create.remind_at
            if remind_at_utc.tzinfo is None:
                remind_at_utc = remind_at_utc.replace(tzinfo=timezone.utc)
                logger.debug("remind_at naive → treated as UTC")
            else:
                # Convert to UTC for storage
                remind_at_utc = remind_at_utc.astimezone(timezone.utc)
                logger.debug(f"remind_at converted to UTC")

            # Calculate remind_at_local using user's timezone
            user_tz = pytz.timezone(user_timezone_str)
            remind_at_local = remind_at_utc.astimezone(user_tz)
            logger.debug(f"remind_at_local calculated: {remind_at_local.isoformat()}")

            # Create internal schema with generated reminder_id
            reminder_create_data = reminder_create.model_dump()
            # Override remind_at with normalized UTC version
            reminder_create_data["remind_at"] = remind_at_utc

            reminder_create_internal = ReminderCreateInternal(
                **reminder_create_data,
                reminder_id=reminder_id,
                remind_at_local=remind_at_local,  # Store local
            )

            logger.debug(
                f"ReminderCreateInternal prepared: agent_id={reminder_create_internal.agent_id}, "
                f"remind_at_utc={remind_at_utc}, remind_at_local={remind_at_local}"
            )

            # Persist to database
            reminder = await self.create(
                db=db,
                object=reminder_create_internal,
                schema_to_select=ReminderRead,
                return_as_model=True,
            )

            logger.debug(
                f"Reminder created successfully: id={reminder.id}, "
                f"reminder_id={reminder.reminder_id}, agent_id={reminder.agent_id}"
            )
            return reminder

        except ValueError as e:
            logger.warning(f"Data transformation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to create reminder from DTO: {str(e)}")
            raise

    async def get_reminder_by_id(
        self,
        db: AsyncSession,
        reminder_id: str,
        include_deleted: bool = False,
    ) -> ReminderRead | None:
        """
        Get reminder by primary key (id).

        Args:
            db: AsyncSession for database operations
            reminder_id: UUID of reminder
            include_deleted: Whether to include soft-deleted reminders (default: False)

        Returns:
            ReminderRead: Reminder data or None if not found

        Raises:
            Exception: If database query fails
        """
        try:
            logger.debug(f"Fetching reminder {reminder_id}")

            filter_kwargs = {}
            if not include_deleted:
                filter_kwargs["is_deleted"] = False

            reminder = await self.get(
                db=db,
                id=reminder_id,
                schema_to_select=ReminderRead,
                return_as_model=True,
                **filter_kwargs,
            )

            logger.debug(f"Reminder {reminder_id} fetched successfully")
            return reminder

        except Exception as e:
            logger.error(f"Failed to fetch reminder {reminder_id}: {str(e)}")
            raise

    async def list_reminders_filtered(
        self,
        db: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        agent_id: str | None = None,
        status: ReminderStatus | None = None,
        return_total_count: bool = True,
    ) -> dict[str, Any]:
        """
        List reminders with pagination and filtering by agent.

        Args:
            db: AsyncSession for database operations
            offset: Pagination offset (default: 0)
            limit: Pagination limit (default: 10)
            agent_id: Filter by agent_id (optional)
            status: Filter by status (optional)
            return_total_count: Include total count (default: True)

        Returns:
            dict: {data: [ReminderListRead], total_count: int}
        Raises:
            Exception: If database query fails
        """
        try:
            logger.debug(f"Listing reminders - offset: {offset}, limit: {limit}")

            filter_kwargs = {"is_deleted": False}

            if agent_id:
                filter_kwargs["agent_id"] = agent_id
                logger.debug(f"Filtering by agent_id: {agent_id}")

            if status:
                filter_kwargs["status"] = status
                logger.debug(f"Filtering by status: {status}")

            result = await self.get_multi(
                db=db,
                offset=offset,
                limit=limit,
                schema_to_select=ReminderListRead,
                return_as_model=True,
                return_total_count=return_total_count,
                **filter_kwargs,
            )

            logger.debug(
                f"Retrieved {len(result.get('data', []))} reminders, "
                f"total: {result.get('total_count', 0)}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to list reminders: {str(e)}")
            raise

    async def update_reminder_safe(
        self,
        db: AsyncSession,
        reminder_id: str,
        reminder_update: ReminderUpdate,
    ) -> ReminderRead:
        """
        Update reminder - only allow update when status is PENDING.

        Args:
            db: AsyncSession for database operations
            reminder_id: UUID of reminder to update
            reminder_update: ReminderUpdate schema with new values

        Returns:
            ReminderRead: Updated reminder data

        Raises:
            ValueError: If reminder status is not PENDING
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Updating reminder {reminder_id}")

            # Check current status
            current_reminder = await self.get_reminder_by_id(db, reminder_id)
            if not current_reminder:
                raise ValueError(f"Reminder {reminder_id} not found")

            if current_reminder.status != ReminderStatus.PENDING:
                raise ValueError(
                    f"Can only update pending reminders. Current status: {current_reminder.status}"
                )

            update_internal = ReminderUpdateInternal(
                **reminder_update.model_dump(exclude_unset=True)
            )

            updated_reminder = await self.update(
                db=db,
                object=update_internal,
                id=reminder_id,
                schema_to_select=ReminderRead,
                return_as_model=True,
            )

            logger.debug(f"Reminder {reminder_id} updated successfully")
            return updated_reminder

        except ValueError as e:
            logger.warning(
                f"Update validation failed for reminder {reminder_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to update reminder {reminder_id}: {str(e)}")
            raise

    async def soft_delete_reminder(
        self,
        db: AsyncSession,
        reminder_id: str,
    ) -> None:
        """
        Soft delete reminder (set is_deleted=True).

        Uses FastCRUD exists() + delete() for clean soft delete.
        Automatically sets is_deleted=True.

        Args:
            db: AsyncSession for database operations
            reminder_id: UUID of reminder to delete

        Returns:
            None

        Raises:
            ValueError: If reminder not found or already deleted
            Exception: If database operation fails
        """
        try:
            logger.info(f"Soft deleting reminder {reminder_id}")

            # Check if reminder exists and not already deleted (1 DB call)
            exists = await self.exists(
                db=db,
                id=reminder_id,
                is_deleted=False,
            )

            if not exists:
                raise ValueError(f"Reminder {reminder_id} not found or already deleted")

            # FastCRUD delete() auto-detects is_deleted and sets it to True (1 DB call)
            await self.delete(db=db, id=reminder_id)

            logger.debug(f"Reminder {reminder_id} soft deleted successfully")

        except ValueError as e:
            logger.warning(
                f"Delete validation failed for reminder {reminder_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to delete reminder {reminder_id}: {str(e)}")
            raise

    async def update_status_by_id(
        self,
        db: AsyncSession,
        reminder_id: str,
        new_status: ReminderStatus,
    ) -> ReminderRead:
        """
        Update reminder status directly without state transition validation.

        Args:
            db: AsyncSession for database operations
            reminder_id: UUID of reminder to update
            new_status: Target ReminderStatus status

        Returns:
            ReminderRead: Updated reminder

        Raises:
            ValueError: If reminder not found
            Exception: If database operation fails
        """
        try:
            logger.debug(f"Updating reminder {reminder_id} status to {new_status}")

            # Check if reminder exists
            current_reminder = await self.get_reminder_by_id(db, reminder_id)
            if not current_reminder:
                raise ValueError(f"Reminder {reminder_id} not found")

            # Prepare update data with timestamp if transitioning to RECEIVED
            update_kwargs = {"status": new_status}

            if new_status == ReminderStatus.RECEIVED:
                update_kwargs["received_at"] = datetime.now(timezone.utc)

            update_data = ReminderUpdateInternal(**update_kwargs)

            updated_reminder = await self.update(
                db=db,
                object=update_data,
                id=reminder_id,
                schema_to_select=ReminderRead,
                return_as_model=True,
            )

            logger.debug(
                f"Reminder {reminder_id} status updated to {new_status} successfully"
            )
            return updated_reminder

        except ValueError as e:
            logger.warning(f"Status update failed for reminder {reminder_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(
                f"Failed to update status for reminder {reminder_id}: {str(e)}"
            )
            raise

    async def list_reminders_with_search(
        self,
        db: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        search_query: str = "",
        device_id: str | None = None,
        status: ReminderStatus | None = None,
        return_total_count: bool = True,
    ) -> dict[str, Any]:
        """
        List reminders with advanced search across multiple fields (content, title).

        Uses FastCRUD _or parameter for multi-field text search at database layer.
        Generates SQL: WHERE (content ILIKE '%q%' OR title ILIKE '%q%') AND device_id=x AND status=y

        Args:
            db: AsyncSession for database operations
            offset: Pagination offset (default: 0)
            limit: Pagination limit (default: 10)
            search_query: Search keyword for content or title (optional)
            device_id: Filter by device_id (optional)
            status: Filter by status (optional)
            return_total_count: Include total count (default: True)

        Returns:
            dict: {data: [ReminderListRead], total_count: int}

        Raises:
            Exception: If database query fails
        """
        try:
            logger.debug(
                f"Listing reminders with search - query: '{search_query}', "
                f"offset: {offset}, limit: {limit}"
            )

            filter_kwargs = {"is_deleted": False}

            if device_id:
                filter_kwargs["device_id"] = device_id
                logger.debug(f"Filtering by device_id: {device_id}")

            if status:
                filter_kwargs["status"] = status
                logger.debug(f"Filtering by status: {status}")

            # Multi-field search using FastCRUD _or parameter
            if search_query:
                search_pattern = f"%{search_query}%"
                search_or = {
                    "content__ilike": search_pattern,
                    "title__ilike": search_pattern,
                }
                logger.debug(f"Searching with pattern: {search_pattern}")

                result = await self.get_multi(
                    db=db,
                    offset=offset,
                    limit=limit,
                    schema_to_select=ReminderListRead,
                    return_as_model=True,
                    return_total_count=return_total_count,
                    _or=search_or,
                    **filter_kwargs,
                )
            else:
                result = await self.get_multi(
                    db=db,
                    offset=offset,
                    limit=limit,
                    schema_to_select=ReminderListRead,
                    return_as_model=True,
                    return_total_count=return_total_count,
                    **filter_kwargs,
                )

            logger.debug(
                f"Retrieved {len(result.get('data', []))} reminders, "
                f"total: {result.get('total_count', 0)}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to list reminders with search: {str(e)}")
            raise

    async def get_reminders_by_device_filtered(
        self,
        db: AsyncSession,
        device_id: str,
        is_today: bool = True,
        status_filter: str = "pending",
    ) -> dict[str, Any]:
        """
        Get reminders for a device filtered by time period and completion status.

        Args:
            db: AsyncSession for database operations
            device_id: UUID of device to filter by
            is_today: True to filter today's reminders, False for this week (default: True)
            status_filter: Filter by completion status:
                - "pending": Chưa hoàn thành (PENDING, DELIVERED) (default)
                - "completed": Hoàn thành (ACKNOWLEDGED, CONSUMED)
                - "all": Tất cả trạng thái

        Returns:
            dict: {data: [ReminderListRead], total_count: int}

        Raises:
            ValueError: If status_filter is invalid
            Exception: If database query fails
        """
        try:
            from datetime import timedelta

            # Validate status_filter
            valid_filters = ["pending", "completed", "all"]
            if status_filter not in valid_filters:
                raise ValueError(
                    f"Invalid status_filter: {status_filter}. "
                    f"Must be one of {valid_filters}"
                )

            logger.info(
                f"Fetching reminders for device {device_id}, "
                f"period: {'today' if is_today else 'this_week'}, "
                f"status: {status_filter}"
            )

            # Calculate date range based on is_today flag
            now = datetime.now(timezone.utc)

            if is_today:
                # Today: from 00:00 to 23:59:59
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
                logger.debug(f"Today range: {start_date} to {end_date}")
            else:
                # This week: from Monday to Sunday
                days_since_monday = now.weekday()
                start_date = (now - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=7)
                logger.debug(f"This week range: {start_date} to {end_date}")

            # Query reminders with filters
            result = await self.get_multi(
                db=db,
                device_id=device_id,
                is_deleted=False,
                schema_to_select=ReminderListRead,
                return_as_model=True,
                return_total_count=True,
            )

            # Filter reminders by remind_at date range and completion status
            filtered_data = []
            pending_statuses = {
                ReminderStatus.PENDING,
                ReminderStatus.DELIVERED,
            }
            completed_statuses = {
                ReminderStatus.RECEIVED,
            }

            for reminder in result.get("data", []):
                remind_at = reminder.remind_at
                # Check time period filter
                if not (start_date <= remind_at < end_date):
                    continue

                # Check completion status filter
                if status_filter == "pending":
                    if reminder.status in pending_statuses:
                        filtered_data.append(reminder)
                elif status_filter == "completed":
                    if reminder.status in completed_statuses:
                        filtered_data.append(reminder)
                elif status_filter == "all":
                    filtered_data.append(reminder)

            logger.debug(
                f"Retrieved {len(filtered_data)} reminders for device {device_id} "
                f"in {'today' if is_today else 'this_week'} with status {status_filter}"
            )

            return {
                "data": filtered_data,
                "total_count": len(filtered_data),
            }

        except ValueError as e:
            logger.warning(f"Status filter validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch reminders for device {device_id}: {str(e)}")
            raise

    async def batch_soft_delete_reminders(
        self,
        db: AsyncSession,
        reminder_ids: list[str],
    ) -> int:
        """
        Soft delete multiple reminders by IDs in batch (set is_deleted=True for each).

        Uses FastCRUD.update() with allow_multiple=True for efficient batch operation.
        Single SQL UPDATE query instead of individual delete() calls.

        Args:
            db: AsyncSession for database operations
            reminder_ids: List of reminder UUIDs to delete

        Returns:
            int: Count of successfully deleted reminders

        Raises:
            ValueError: If reminder_ids is empty
            Exception: If batch operation fails critically
        """
        try:
            if not reminder_ids:
                raise ValueError("reminder_ids list cannot be empty")

            logger.debug(f"Batch soft deleting {len(reminder_ids)} reminders")

            # Use FastCRUD.update() with allow_multiple=True for batch soft delete
            # Generates: UPDATE reminder SET is_deleted=True WHERE id IN (...)
            deleted_count = await self.update(
                db=db,
                object={"is_deleted": True},
                allow_multiple=True,
                id__in=reminder_ids,
            )

            logger.debug(
                f"Batch soft delete completed: {deleted_count} reminders deleted"
            )
            return deleted_count

        except ValueError as e:
            logger.warning(f"Batch delete validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to batch delete reminders: {str(e)}")
            raise

    async def batch_hard_delete_reminders(
        self,
        db: AsyncSession,
        reminder_ids: list[str],
    ) -> int:
        """
        Permanently delete multiple reminders from database (hard delete, no recovery).

        Uses FastCRUD.db_delete() with allow_multiple=True for efficient batch operation.
        Single SQL DELETE query - records cannot be recovered.

        WARNING: This is permanent deletion. Use soft_delete_reminder for reversible deletes.

        Args:
            db: AsyncSession for database operations
            reminder_ids: List of reminder UUIDs to delete permanently

        Returns:
            int: Count of successfully deleted reminders

        Raises:
            ValueError: If reminder_ids is empty
            Exception: If batch operation fails critically
        """
        try:
            if not reminder_ids:
                raise ValueError("reminder_ids list cannot be empty")

            logger.warning(
                f"Batch hard deleting {len(reminder_ids)} reminders (PERMANENT, no recovery)"
            )

            # Use FastCRUD.db_delete() with allow_multiple=True for batch hard delete
            # Generates: DELETE FROM reminder WHERE id IN (...)
            deleted_count = await self.db_delete(
                db=db,
                allow_multiple=True,
                id__in=reminder_ids,
            )

            logger.warning(
                f"Batch hard delete completed: {deleted_count} reminders permanently deleted"
            )
            return deleted_count

        except ValueError as e:
            logger.warning(f"Batch hard delete validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to batch hard delete reminders: {str(e)}")
            raise


crud_reminders = CRUDReminders(Reminder)
