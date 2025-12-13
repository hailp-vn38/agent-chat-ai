import inspect
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .config import Settings, load_config
from .core.auth import AuthManager
from .core.config import settings
from .core.logger import setup_logging
from .ai.module_factory import initialize_modules
from .core.setup import create_application, lifespan_factory
from .core.uvicorn_config import setup_uvicorn_logging
from .services import ThreadPoolService, ReminderService, scheduler_service, MQTTService

# Thiết lập logging từ đầu
setup_logging()
setup_uvicorn_logging()


async def startup_realtime_components(app: FastAPI) -> None:
    """Khởi tạo ThreadPool, AuthManager, và các mô-đun realtime."""
    logger = setup_logging().bind(tag=__name__)

    raw_config = load_config()
    module_settings = Settings.from_dict(raw_config)
    app.state.config = module_settings

    max_workers = raw_config.get("thread_pool", {}).get("max_workers", 10)
    app.state.thread_pool = ThreadPoolService(max_workers=max_workers)
    app.state.active_connections = set()
    app.state.modules = {}
    app.state.auth_manager = None
    app.state.reminder_service = None
    app.state.mqtt_service = None

    if module_settings.auth.enabled:
        try:
            app.state.auth_manager = AuthManager(
                secret_key=module_settings.server.auth_key,
                expire_seconds=module_settings.auth.expire_seconds,
            )
            logger.info("[Startup] AuthManager initialized (auth enabled)")
        except Exception as exc:
            logger.warning(f"[Startup] Failed to initialize AuthManager: {exc}")
            app.state.auth_manager = None
    else:
        logger.debug("[Startup] Auth disabled")

    # Initialize MQTT service (trước reminder vì reminder có thể dùng)
    try:
        mqtt_service = MQTTService.from_config(module_settings.mqtt)
        await mqtt_service.start()
        app.state.mqtt_service = mqtt_service
        if mqtt_service.is_available():
            logger.info("[Startup] MQTT service initialized")
        else:
            logger.debug("[Startup] MQTT service running in degraded mode (no config)")
    except Exception as exc:
        logger.warning(f"[Startup] Failed to initialize MQTT service: {exc}")
        app.state.mqtt_service = None

    try:
        modules = await initialize_modules(
            thread_pool=app.state.thread_pool,
            config=module_settings,
        )
        app.state.modules = modules
        logger.info(f"[Startup] Modules initialized: {list(modules.keys())}")
    except Exception as exc:
        logger.error(f"[Startup] Module initialization failed: {exc}")
        traceback.print_exc()
        app.state.modules = {}

    try:
        reminder_service = ReminderService(
            reminder_config=module_settings.reminder,
            server_config=module_settings.server,
            mqtt_service=app.state.mqtt_service,
        )
        reminder_service.init_app(app)
        app.state.reminder_service = reminder_service
        logger.info("[Startup] Reminder service initialized")
    except Exception as exc:
        logger.warning(f"[Startup] Failed to initialize Reminder service: {exc}")
        app.state.reminder_service = None

    # Initialize scheduler service for cleanup jobs
    try:
        await scheduler_service.start()
        app.state.scheduler_service = scheduler_service
        logger.info("[Startup] Cleanup scheduler service đã khởi động")
    except Exception as exc:
        logger.warning(f"[Startup] Không thể khởi động scheduler service: {exc}")
        app.state.scheduler_service = None


async def shutdown_realtime_components(app: FastAPI) -> None:
    """Giải phóng tài nguyên realtime khi shutdown."""
    logger = setup_logging().bind(tag=__name__)

    modules = getattr(app.state, "modules", {}) or {}
    thread_pool: ThreadPoolService | None = getattr(app.state, "thread_pool", None)
    reminder_service: ReminderService | None = getattr(
        app.state, "reminder_service", None
    )
    scheduler_service_instance = getattr(app.state, "scheduler_service", None)
    mqtt_service: MQTTService | None = getattr(app.state, "mqtt_service", None)

    # Shutdown scheduler service first
    if scheduler_service_instance:
        try:
            await scheduler_service_instance.shutdown()
            logger.info("[Shutdown] Cleanup scheduler đã shutdown")
        except Exception as exc:
            logger.warning(f"[Shutdown] Lỗi khi shutdown scheduler service: {exc}")

    # Shutdown reminder service trước để cleanup scheduler semaphores
    if reminder_service:
        try:
            await reminder_service.shutdown()
            logger.info("[Shutdown] Reminder service shutdown completed")
        except Exception as exc:
            logger.warning(f"[Shutdown] Error shutting down reminder service: {exc}")

    # Shutdown MQTT service sau reminder (reminder dùng MQTT)
    if mqtt_service:
        try:
            await mqtt_service.shutdown()
            logger.info("[Shutdown] MQTT service shutdown completed")
        except Exception as exc:
            logger.warning(f"[Shutdown] Error shutting down MQTT service: {exc}")

    # Close modules
    for module_name, module in modules.items():
        close_callable = getattr(module, "close", None)
        if not close_callable:
            continue
        try:
            if inspect.iscoroutinefunction(close_callable) or hasattr(
                close_callable, "__await__"
            ):
                await close_callable()
            elif thread_pool:
                await thread_pool.run_blocking(close_callable)
            else:
                close_callable()
            logger.info(f"[Shutdown] Closed module: {module_name}")
        except Exception as exc:
            logger.warning(f"[Shutdown] Error closing module {module_name}: {exc}")

    # Shutdown ThreadPool với wait=True để cleanup semaphores
    if thread_pool:
        thread_pool.shutdown(wait=True)
        logger.info("[Shutdown] ThreadPool shutdown completed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Custom lifespan for the application."""
    default_lifespan = lifespan_factory(settings)

    async with default_lifespan(app):
        await startup_realtime_components(app)
        try:
            yield
        finally:
            await shutdown_realtime_components(app)


app = create_application(router=router, settings=settings, lifespan=lifespan)
