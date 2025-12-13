"""
AgentService - Centralized business logic for agent domain operations.

Consolidates all agent-related logic including:
- Device + Agent + Template queries via AgentTemplateAssignment junction
- Template transformation for WebSocket communication
- Device connection status management (DB + Redis cache)
- Template validation and availability checks

Dependencies:
- CRUD: crud_agent, crud_device
- Cache: BaseCacheManager (Redis)
- Logger: Structured logging for troubleshooting
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.logger import get_logger
from ..core.utils.cache import BaseCacheManager
from ..crud.crud_agent import crud_agent
from ..crud.crud_device import crud_device
from ..schemas.agent import AgentRead
from ..schemas.device import DeviceRead
from ..ai.utils.device_connection_utils import is_device_online
from ..ai.handle.textHandler.notificationMessageHandler import (
    NotificationMessageHandler,
)

logger = get_logger(__name__)


class DeviceStatusManager:
    """
    Manages device connection status atomically with DB + cache synchronization.

    Responsibilities:
    - Update device connection timestamps in DB (source of truth)
    - Manage device status cache with TTL
    - Handle cache/DB sync errors gracefully (DB is primary)
    - Provide structured logging for troubleshooting

    Note: This is an inner class of AgentService for focused responsibility
    and reuse of parent's logger/cache context.
    """

    def __init__(self, service: "AgentService", cache_manager: BaseCacheManager):
        """
        Initialize DeviceStatusManager.

        Args:
            service: Parent AgentService instance for context
            cache_manager: BaseCacheManager for Redis operations
        """
        self.service = service
        self.cache_manager = cache_manager
        self.logger = get_logger(__name__)

    async def mark_connected(
        self,
        db: AsyncSession,
        device_id: str,
        ttl: Optional[int] = None,
    ) -> Optional[DeviceRead]:
        """
        Mark device as connected atomically (DB + cache).

        Flow:
        1. Check if device exists in DB
        2. Update DB: set device.last_connected_at = now (if exists)
        3. Set cache: device:{device_id}:status WITHOUT TTL (expires only on disconnect)

        On cache failure: logs warning but continues (cache is non-critical)
        On DB failure: logs warning, skips DB update but still caches (graceful degradation)

        Args:
            db: AsyncSession for database operations
            device_id: Device UUID
            ttl: Cache TTL in seconds. None (default) = no expiration. Cache only deleted on WS disconnect.

        Returns:
            Optional[DeviceRead]: Updated device record if exists, None if device not found

        Note:
            This method gracefully handles missing devices (returns None instead of raising)
            to support devices that may not be fully provisioned yet. Cache is still updated
            to track connection for diagnostic purposes.
        """
        try:
            self.logger.debug(f"Marking device {device_id} as connected")

            # Step 1: Update DB (source of truth) - but gracefully handle missing device
            from ..schemas.device import DeviceUpdateInternal

            now = datetime.now(timezone.utc)
            device = None

            try:
                update_data = DeviceUpdateInternal(
                    last_connected_at=now,
                    updated_at=now,
                )

                device = await crud_device.update(
                    db=db,
                    object=update_data,
                    id=device_id,
                    schema_to_select=DeviceRead,
                    return_as_model=True,
                )

                self.logger.info(
                    f"Device {device_id} DB updated: last_connected_at = {now}"
                )
            except Exception as db_error:
                # Device not found or update failed: log warning but continue with cache
                self.logger.warning(
                    f"DB update failed for device {device_id}: {str(db_error)}. "
                    f"Continuing with cache-only tracking."
                )

            # Step 2: Update cache (best-effort, non-critical)
            # Always try to cache even if DB failed (for diagnostic purposes)
            try:
                cache_key = f"device:{device_id}:status"
                cache_value = {
                    "connected_at": now.isoformat(),
                    "device_id": str(device_id),
                    "from_db": device is not None,
                }

                await self.cache_manager.set(
                    key=cache_key,
                    value=cache_value,
                    ttl=ttl,
                )

                self.logger.debug(
                    f"Device {device_id} cached (no TTL - persistent until disconnect)"
                )

            except Exception as cache_error:
                # Cache failure is non-critical: log warning but don't raise
                self.logger.warning(
                    f"Cache write failed for device {device_id}: {str(cache_error)}. "
                    f"Connection tracking may be incomplete."
                )

            return device

        except Exception as e:
            self.logger.error(
                f"Failed to mark device {device_id} as connected: {str(e)}"
            )
            # Don't raise - return None to indicate device not found but continue operation
            return None

    async def mark_disconnected(
        self,
        db: AsyncSession,
        device_id: str,
    ) -> None:
        """
        Mark device as disconnected (cleanup cache, optionally update DB).

        Flow:
        1. Delete cache: remove device:{device_id}:status
        2. Optionally update DB: mark device offline

        Note: Cache cleanup is non-critical; logs warnings on failure but continues

        Args:
            db: AsyncSession for database operations
            device_id: Device UUID
        """
        try:
            self.logger.debug(f"Marking device {device_id} as disconnected")

            # Step 1: Clean up cache (non-critical)
            try:
                cache_key = f"device:{device_id}:status"
                await self.cache_manager.delete(cache_key)
                self.logger.debug(f"Device {device_id} cache cleaned")

            except Exception as cache_error:
                self.logger.warning(
                    f"Cache delete failed for device {device_id}: {str(cache_error)}. "
                    f"Continuing (will auto-expire on TTL)"
                )

            # Optional: Update DB if needed
            # Currently, we don't update DB on disconnect (just cache cleanup)
            # Can be extended in future for "offline" status tracking

            self.logger.info(f"Device {device_id} marked as disconnected")

        except Exception as e:
            self.logger.error(
                f"Failed to mark device {device_id} as disconnected: {str(e)}"
            )
            # Don't raise: cleanup is non-critical

    async def get_status(
        self,
        db: AsyncSession,
        device_id: str,
    ) -> Optional[dict]:
        """
        Query device connection status from cache or DB.

        Priority:
        1. Check cache first (fast path)
        2. Fallback to DB query (slow path)

        Args:
            db: AsyncSession for database operations
            device_id: Device UUID

        Returns:
            dict: Status info (from cache or DB), None if device not found
        """
        try:
            cache_key = f"device:{device_id}:status"

            # Try cache first
            try:
                cached_status = await self.cache_manager.get(cache_key)
                if cached_status:
                    self.logger.debug(f"Device {device_id} status from cache")
                    return cached_status
            except Exception as cache_error:
                self.logger.debug(
                    f"Cache read failed for {device_id}: {str(cache_error)}"
                )

            # Fallback to DB
            device = await crud_device.get(
                db=db,
                id=device_id,
                schema_to_select=DeviceRead,
                return_as_model=True,
            )

            if device:
                status = {
                    "device_id": str(device_id),
                    "last_connected_at": (
                        device.last_connected_at.isoformat()
                        if device.last_connected_at
                        else None
                    ),
                }
                self.logger.debug(f"Device {device_id} status from DB")
                return status

            return None

        except Exception as e:
            self.logger.error(f"Failed to get device {device_id} status: {str(e)}")
            return None


class AgentService:
    """
    Service for agent domain operations.

    Provides methods for:
    - Querying agents by MAC address with full relations
    - Transforming templates for WebSocket communication
    - Managing template changes and validation
    - Tracking device connection status (DB + cache)
    """

    def __init__(self, cache_manager: Optional[BaseCacheManager] = None):
        """Initialize AgentService with CRUD instances and optional cache manager."""
        self._cache_manager = cache_manager
        self._device_status_manager: Optional[DeviceStatusManager] = None

    @property
    def cache_manager(self) -> Optional[BaseCacheManager]:
        """Get or lazily initialize cache manager."""
        if self._cache_manager is None:
            # Lazy load cache manager if needed
            try:
                from ..core.utils.cache import get_cache_manager

                self._cache_manager = get_cache_manager()
            except Exception:
                logger.debug("Cache manager not available, continuing without cache")
        return self._cache_manager

    @property
    def device_status(self) -> DeviceStatusManager:
        """Get or lazily initialize device status manager."""
        if self._device_status_manager is None:
            if self.cache_manager:
                self._device_status_manager = DeviceStatusManager(
                    self, self.cache_manager
                )
            else:
                raise RuntimeError(
                    "DeviceStatusManager requires cache_manager. "
                    "Ensure cache is configured in application settings."
                )
        return self._device_status_manager

    async def get_agent_from_ws(
        self,
        db: AsyncSession,
        mac_address: str,
    ) -> dict | None:
        """
        Get agent with device, template, and provider configs for WebSocket connection.

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
            None: If agent not found
        """
        try:
            logger.debug(f"Fetching agent for WebSocket by mac_address: {mac_address}")

            # Get agent with device, template, and provider configs
            result = await crud_agent.get_agent_by_mac_address(
                db=db,
                mac_address=mac_address,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get agent for WebSocket {mac_address}: {str(e)}")
            # Return safe default on error instead of raising (non-critical for WebSocket)
            return None

    # ==================== Template Management Methods ====================

    async def change_agent_template(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
    ) -> AgentRead:
        """
        Update agent's active template.

        Args:
            db: AsyncSession for database operations
            agent_id: UUID of agent to update
            template_id: UUID of new template

        Returns:
            AgentRead: Updated agent with new template_id

        Raises:
            ValueError: If agent not found

        Example:
            updated_agent = await service.change_agent_template(
                db, agent_id, new_template_id
            )
        """
        try:
            logger.debug(f"Changing template for agent {agent_id} to {template_id}")

            # Prepare update data with current timestamp
            from ..schemas.agent import AgentUpdateInternal

            # Update agent
            agent = await crud_agent.change_agent_template(
                db=db,
                agent_id=agent_id,
                template_id=template_id,
            )

            logger.info(f"Agent {agent_id} template changed to {template_id}")
            return agent

        except Exception as e:
            logger.error(f"Failed to change agent template for {agent_id}: {str(e)}")
            raise

    async def validate_template_belongs_to_agent(
        self,
        db: AsyncSession,
        agent_id: str,
        template_id: str,
    ) -> bool:
        """
        Verify template is assigned to agent.

        Checks if assignment exists in AgentTemplateAssignment table
        for the given agent and template.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            template_id: Template UUID

        Returns:
            bool: True if template is assigned to agent, else False

        Example:
            is_valid = await service.validate_template_belongs_to_agent(
                db, agent_id, template_id
            )
            if not is_valid:
                raise ValueError("Template is not assigned to agent")
        """
        try:
            logger.debug(
                f"Validating template {template_id} assigned to agent {agent_id}"
            )

            from sqlalchemy import select
            from ..models.agent_template_assignment import AgentTemplateAssignment

            # Check if assignment exists
            stmt = select(AgentTemplateAssignment).where(
                AgentTemplateAssignment.agent_id == agent_id,
                AgentTemplateAssignment.template_id == template_id,
            )

            result = await db.execute(stmt)
            assignment = result.scalar_one_or_none()

            is_valid = assignment is not None

            if is_valid:
                logger.debug(f"Template {template_id} is assigned to agent {agent_id}")
            else:
                logger.warning(
                    f"Template {template_id} is NOT assigned to agent {agent_id}"
                )

            return is_valid

        except Exception as e:
            logger.error(
                f"Failed to validate template {template_id} for agent {agent_id}: {str(e)}"
            )
            return False

    async def get_transformed_template(
        self,
        db: AsyncSession,
        template_id: str,
    ) -> dict | None:
        """
        Get template and transform for WebSocket communication.

        Fetches Template model (the new shareable template structure)
        and returns dict with all fields needed for WebSocket.

        Args:
            db: AsyncSession for database operations
            template_id: Template UUID

        Returns:
            dict: Full template data with all provider fields
            {
                "id": "...",
                "name": "...",
                "prompt": "...",
                "ASR": "...",
                "LLM": "...",
                ...
            }

        Returns None if template not found.

        Example:
            transformed = await service.get_transformed_template(db, template_id)
            if transformed:
                print(f"Template: {transformed['name']}")
        """
        try:
            logger.debug(f"Fetching and transforming template {template_id}")

            from ..models.template import Template
            from sqlalchemy import select

            # Fetch template using raw SQLAlchemy for flexibility
            stmt = select(Template).where(
                Template.id == template_id,
                Template.is_deleted == False,
            )

            result = await db.execute(stmt)
            template = result.scalar_one_or_none()

            if not template:
                logger.debug(f"Template {template_id} not found")
                return None

            # Convert to dict for WebSocket use
            template_dict = {
                "id": str(template.id),
                "name": template.name,
                "prompt": template.prompt,
                "ASR": template.ASR,
                "LLM": template.LLM,
                "VLLM": template.VLLM,
                "TTS": template.TTS,
                "Memory": template.Memory,
                "Intent": template.Intent,
                "tools": template.tools,
                "summary_memory": template.summary_memory,
                "is_public": template.is_public,
            }

            logger.debug(f"Template {template_id} transformed successfully")
            return template_dict

        except Exception as e:
            logger.error(
                f"Failed to get and transform template {template_id}: {str(e)}"
            )
            return None

    async def get_available_templates_for_ws(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get list of templates assigned to agent, formatted for WebSocket.

        Queries Template model via AgentTemplateAssignment junction table.
        Returns only templates that are explicitly assigned to the agent.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            offset: Pagination offset (0-indexed)
            limit: Pagination limit (max records per page)

        Returns:
            list[dict]: List of template dicts with id and name fields

        Example:
            templates = await service.get_available_templates_for_ws(
                db, agent_id, limit=20
            )
            # Returns: [{"id": "uuid1", "name": "template1", "is_active": true}, ...]
        """
        try:
            logger.debug(
                f"Fetching assigned templates for agent {agent_id}, "
                f"offset: {offset}, limit: {limit}"
            )

            from sqlalchemy import select, func
            from ..models.template import Template
            from ..models.agent_template_assignment import AgentTemplateAssignment

            # Query: templates with is_active from assignment table
            stmt = (
                select(Template, AgentTemplateAssignment.is_active)
                .join(
                    AgentTemplateAssignment,
                    Template.id == AgentTemplateAssignment.template_id,
                )
                .where(
                    AgentTemplateAssignment.agent_id == agent_id,
                    Template.is_deleted == False,
                )
                .offset(offset)
                .limit(limit)
            )

            count_stmt = (
                select(func.count())
                .select_from(Template)
                .join(
                    AgentTemplateAssignment,
                    Template.id == AgentTemplateAssignment.template_id,
                )
                .where(
                    AgentTemplateAssignment.agent_id == agent_id,
                    Template.is_deleted == False,
                )
            )

            # Execute queries
            result = await db.execute(stmt)
            rows = result.all()  # Returns list of (Template, is_active) tuples

            count_result = await db.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Extract id, name, and is_active from each row
            available_templates = []
            for template, is_active in rows:
                template_id = str(template.id) if template.id else None
                available_templates.append(
                    {
                        "id": template_id,
                        "name": template.name,
                        "is_active": is_active,
                    }
                )

            logger.info(
                f"Successfully fetched {len(available_templates)} assigned templates "
                f"for agent {agent_id} (total: {total_count})"
            )

            return available_templates

        except Exception as e:
            logger.error(
                f"Failed to get available templates for agent {agent_id}: {str(e)}"
            )
            raise

    # ==================== Device Status Methods ====================

    async def update_device_connection_status(
        self,
        db: AsyncSession,
        device_id: str,
    ) -> Optional[DeviceRead]:
        """
        Update device's last connection timestamp.

        ⚠️ REFACTORED: Now uses DeviceStatusManager internally.
        Signature changed: mac_address → device_id for consistency.

        This method is now a wrapper around DeviceStatusManager.mark_connected()
        for backward compatibility. New code should use:
        `await service.device_status.mark_connected(db, device_id)`

        Args:
            db: AsyncSession for database operations
            device_id: Device UUID

        Returns:
            Optional[DeviceRead]: Updated device if exists, None if device not found

        Note:
            This method gracefully handles missing devices by returning None
            instead of raising. Cache is still updated for diagnostic purposes.

        Example:
            updated_device = await service.update_device_connection_status(db, device_id)
            if updated_device:
                print(f"Last connected: {updated_device.last_connected_at}")
            else:
                print("Device not found in database")
        """
        try:
            logger.debug(f"Updating connection status for device {device_id}")

            # Delegate to DeviceStatusManager
            device = await self.device_status.mark_connected(db, device_id)

            if device:
                logger.info(f"Device {device_id} connection status updated")
            else:
                logger.warning(
                    f"Device {device_id} not found in DB, but cached for tracking"
                )

            return device

        except Exception as e:
            logger.error(
                f"Failed to update device connection status for {device_id}: {str(e)}"
            )
            # Don't raise - return None to allow graceful degradation
            return None

    # ==================== Chat Message Methods ====================

    async def save_chat_message(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
        chat_type: int,
        content: str,
    ) -> bool:
        """
        Save a chat message to database.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            session_id: Session UUID (group messages)
            chat_type: 1 = user, 2 = assistant
            content: Message text content

        Returns:
            bool: True if saved successfully, False on error
        """
        try:
            from ..crud.crud_agent_message import crud_agent_message

            await crud_agent_message.create_message(
                db=db,
                agent_id=agent_id,
                session_id=session_id,
                chat_type=chat_type,
                content=content,
            )

            logger.debug(
                f"Saved message for agent {agent_id}, session {session_id}, type {chat_type}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save chat message: {str(e)}")
            return False

    async def get_chat_history(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Get paginated chat history for an agent.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            offset: Pagination offset
            limit: Max records per page

        Returns:
            dict: {"data": list[AgentMessageRead], "total_count": int}
        """
        try:
            from ..crud.crud_agent_message import crud_agent_message

            result = await crud_agent_message.get_messages_by_agent(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get chat history for agent {agent_id}: {str(e)}")
            raise

    async def get_chat_session(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        Get messages for a specific session.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            session_id: Session UUID
            offset: Pagination offset
            limit: Max records per page

        Returns:
            dict: {"data": list[AgentMessageRead], "total_count": int}
        """
        try:
            from ..crud.crud_agent_message import crud_agent_message

            result = await crud_agent_message.get_messages_by_session(
                db=db,
                agent_id=agent_id,
                session_id=session_id,
                offset=offset,
                limit=limit,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {str(e)}")
            raise

    async def get_chat_sessions(
        self,
        db: AsyncSession,
        agent_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        Get list of chat sessions for an agent.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            offset: Pagination offset
            limit: Max records per page

        Returns:
            dict: {"data": list[SessionSummary], "total_count": int}
        """
        try:
            from ..crud.crud_agent_message import crud_agent_message

            result = await crud_agent_message.get_sessions_by_agent(
                db=db,
                agent_id=agent_id,
                offset=offset,
                limit=limit,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to get sessions for agent {agent_id}: {str(e)}")
            raise

    async def delete_chat_history(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str | None = None,
    ) -> int:
        """Delete chat history for an agent or specific session."""
        try:
            # Implementation here
            return 0
        except Exception as e:
            logger.error(f"Failed to delete chat history: {str(e)}")
            raise

    async def push_agent_notification(
        self,
        db: AsyncSession,
        agent_id: str,
        device_id: str,
        mac_address: str,
        payload: dict[str, Any],
        mqtt_service: Optional[Any] = None,
        app_state: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Push notification to device via WebSocket or MQTT.

        Follows the same delivery pattern as reminder service:
        1. Check if device is online
        2. If online: Try WebSocket first, fallback to MQTT
        3. If offline: Use MQTT only

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID (for logging/validation)
            device_id: Device UUID
            mac_address: Device MAC address (for MQTT topic)
            payload: Notification payload dict with type, useLLM, title, content
            mqtt_service: MQTTService instance (optional)
            app_state: FastAPI app state for active_connections (optional)

        Returns:
            dict: {
                "delivered": bool - True if delivered (WS or MQTT)
                "method": str - "WS", "MQTT", or None if no method worked
                "error": str | None - Error message if delivery failed
            }

        Note:
            - Never raises exceptions (graceful degradation)
            - Returns 202 Accepted scenario when device offline + MQTT unavailable
            - Reuses NotificationMessageHandler from reminder service
        """
        logger.debug(
            f"[Notification] Pushing to agent={agent_id}, device={device_id}, "
            f"mac={mac_address}"
        )

        delivery_method = None
        delivery_sent = False
        error_msg = None

        try:
            # Check device online status
            device_online = await is_device_online(device_id)

            # Check MQTT availability (sync method)
            mqtt_available = mqtt_service.is_available() if mqtt_service else False

            if device_online:
                # Device online: Try WebSocket first
                logger.debug(
                    f"[Notification] Device {device_id} is online, attempting WebSocket"
                )

                # Find ConnectionHandler from active_connections
                active_connections = (
                    getattr(app_state, "active_connections", set())
                    if app_state
                    else set()
                )

                notification_handler = NotificationMessageHandler()
                ws_sent = False

                for handler in active_connections:
                    # Match device by device_id
                    if str(handler.device_id) == str(device_id):
                        try:
                            loop = getattr(handler, "loop", None)
                            if loop is None or not loop.is_running():
                                logger.debug(
                                    f"[Notification] Handler loop not running for {device_id}"
                                )
                                continue

                            coro = notification_handler.handle(handler, payload)
                            asyncio.run_coroutine_threadsafe(coro, loop)
                            logger.info(
                                f"[Notification] WebSocket delivery successful for device {device_id}"
                            )
                            ws_sent = True
                            delivery_method = "WS"
                            delivery_sent = True
                            break
                        except Exception as ws_exc:
                            logger.warning(
                                f"[Notification] WebSocket delivery failed for {device_id}: {ws_exc}"
                            )

                # WebSocket not successful, fallback to MQTT if available
                if not ws_sent and mqtt_available:
                    logger.debug(
                        f"[Notification] WebSocket unavailable for {device_id}, "
                        f"falling back to MQTT"
                    )
                    try:
                        # Build MQTT topic: device/{mac_address}
                        topic = f"device/{mac_address}"
                        success = await mqtt_service.publish(topic, payload)
                        if success:
                            delivery_method = "MQTT"
                            delivery_sent = True
                            logger.info(
                                f"[Notification] MQTT delivery successful to {topic}"
                            )
                        else:
                            error_msg = "MQTT publish returned False"
                            logger.warning(
                                f"[Notification] MQTT publish failed for {topic}"
                            )
                    except Exception as mqtt_exc:
                        error_msg = f"MQTT publish error: {str(mqtt_exc)}"
                        logger.warning(
                            f"[Notification] MQTT publish failed: {mqtt_exc}"
                        )

                # If still not sent and MQTT unavailable
                if not delivery_sent and not mqtt_available:
                    error_msg = "WebSocket unavailable, MQTT not configured"
                    logger.warning(
                        f"[Notification] Device {device_id} online but no delivery "
                        f"method available"
                    )
            else:
                # Device offline: Use MQTT only
                if mqtt_available:
                    logger.debug(
                        f"[Notification] Device {device_id} is offline, using MQTT"
                    )
                    try:
                        topic = f"device/{mac_address}"
                        success = await mqtt_service.publish(topic, payload)
                        if success:
                            delivery_method = "MQTT"
                            delivery_sent = True
                            logger.info(
                                f"[Notification] MQTT delivery successful to {topic}"
                            )
                        else:
                            error_msg = "MQTT publish returned False"
                            logger.warning(
                                f"[Notification] MQTT publish failed for {topic}"
                            )
                    except Exception as mqtt_exc:
                        error_msg = f"MQTT publish error: {str(mqtt_exc)}"
                        logger.warning(
                            f"[Notification] MQTT publish failed: {mqtt_exc}"
                        )
                else:
                    error_msg = "Device offline, MQTT not available"
                    logger.warning(
                        f"[Notification] Device {device_id} offline and "
                        f"MQTT not available"
                    )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"[Notification] Unexpected error: {e}")

        return {
            "delivered": delivery_sent,
            "method": delivery_method,
            "error": error_msg if not delivery_sent else None,
        }

    async def delete_chat_history(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str | None = None,
    ) -> int:
        """
        Delete chat history for an agent or specific session.

        Args:
            db: AsyncSession for database operations
            agent_id: Agent UUID
            session_id: Optional session UUID (if None, deletes all)

        Returns:
            int: Number of deleted messages
        """
        try:
            from ..crud.crud_agent_message import crud_agent_message

            if session_id:
                count = await crud_agent_message.delete_by_session(
                    db=db,
                    agent_id=agent_id,
                    session_id=session_id,
                )
            else:
                count = await crud_agent_message.delete_by_agent(
                    db=db,
                    agent_id=agent_id,
                )

            logger.info(
                f"Deleted {count} messages for agent {agent_id}"
                + (f", session {session_id}" if session_id else "")
            )
            return count

        except Exception as e:
            logger.error(f"Failed to delete chat history: {str(e)}")
            raise


# Export service instance for dependency injection
agent_service = AgentService()
