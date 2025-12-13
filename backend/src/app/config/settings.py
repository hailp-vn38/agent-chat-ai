from copy import deepcopy
from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class ServerSettings(BaseSettings):
    """Cấu hình máy chủ"""

    ip: str = "0.0.0.0"
    port: int = 8003
    http_port: int = 8003
    auth_key: str = ""
    tz: str = "UTC"

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _migrate_timezone(cls, data):
        if isinstance(data, dict):
            if "tz" not in data and "timezone_offset" in data:
                data = dict(data)
                data["tz"] = str(data["timezone_offset"])
        return data

    @field_validator("tz", mode="before")
    @classmethod
    def _coerce_timezone(cls, value):
        if value is None or value == "":
            return "UTC"
        return str(value)


class AuthSettings(BaseSettings):
    """Cấu hình xác thực"""

    enabled: bool = False
    allowed_devices: list = Field(default_factory=list)
    expire_seconds: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class MQTTSettings(BaseSettings):
    """Cấu hình MQTT chung cho toàn ứng dụng.

    Đây là class cấu hình MQTT tập trung, có thể tái sử dụng cho nhiều module
    (reminder, notification, IoT control, etc.).

    Attributes:
        url: MQTT broker URL (e.g. mqtt://localhost:1883 hoặc mqtts://broker.com:8883)
        username: Username để xác thực với broker (optional)
        password: Password để xác thực với broker (optional)
        keepalive: Thời gian keepalive connection (giây)
        reconnect_min_delay: Thời gian chờ tối thiểu khi reconnect (giây)
        reconnect_max_delay: Thời gian chờ tối đa khi reconnect (giây)

    Example:
        ```yaml
        mqtt:
          url: "mqtt://localhost:1883"
          username: "user"
          password: "pass"
        ```
    """

    url: str = Field(
        default="",
        description="MQTT broker URL (mqtt:// hoặc mqtts://)",
    )
    username: str = Field(default="", description="Username xác thực MQTT")
    password: str = Field(default="", description="Password xác thực MQTT")
    keepalive: int = Field(default=60, description="Keepalive interval (giây)", ge=10)
    reconnect_min_delay: int = Field(
        default=2, description="Min delay khi reconnect (giây)", ge=1
    )
    reconnect_max_delay: int = Field(
        default=30, description="Max delay khi reconnect (giây)", ge=5
    )

    model_config = ConfigDict(extra="allow")


class ReminderMQTTSettings(BaseSettings):
    """Cấu hình MQTT cho dịch vụ nhắc nhở (deprecated, dùng MQTTSettings thay thế)"""

    tts_mqtt_url: str = "mqtt://localhost:1883"
    username: str = ""
    password: str = ""
    topic_base: str = "reminder"

    model_config = ConfigDict(extra="allow")


class ReminderJobStoreSettings(BaseSettings):
    """Cấu hình kho lưu trữ job cho APScheduler"""

    folder: str = "data/reminder_jobs"
    filename: str = "reminders.sqlite"

    model_config = ConfigDict(extra="allow")


class ReminderSchedulerSettings(BaseSettings):
    """Cấu hình scheduler"""

    job_store: ReminderJobStoreSettings = Field(
        default_factory=ReminderJobStoreSettings
    )
    # Ngưỡng thời gian (giây) để xem job là "missed" (default: 5s)
    missed_job_threshold: int = 5

    model_config = ConfigDict(extra="allow")


class ReminderSettings(BaseSettings):
    """Cấu hình tổng thể cho dịch vụ nhắc nhở"""

    mqtt: Optional[ReminderMQTTSettings] = Field(default_factory=ReminderMQTTSettings)
    scheduler: ReminderSchedulerSettings = Field(
        default_factory=ReminderSchedulerSettings
    )
    service_key: str = "reminder-service-default"
    prompt: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("mqtt", mode="before")
    @classmethod
    def _coerce_mqtt(cls, value):
        """Convert None hoặc dict không hợp lệ thành ReminderMQTTSettings default"""
        if value is None or (isinstance(value, dict) and not value):
            return ReminderMQTTSettings()
        return value


class OpenMemorySettings(BaseSettings):
    """Cấu hình OpenMemory service cho Knowledge Base"""

    base_url: str = Field(
        default="http://localhost:8080",
        description="OpenMemory server URL",
    )
    api_key: str = Field(
        default="",
        description="API key for OpenMemory authentication",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
        ge=1,
        le=300,
    )
    enabled: bool = Field(
        default=True,
        description="Enable/disable OpenMemory integration",
    )

    model_config = ConfigDict(
        extra="allow",
        env_prefix="OPENMEMORY_",
    )


class Settings(BaseSettings):
    """Cấu hình chính ứng dụng"""

    # Server config
    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)

    # Modules
    selected_module: Dict[str, str] = Field(default_factory=dict)

    # MQTT config (shared)
    mqtt: Optional[MQTTSettings] = Field(
        default=None,
        description="MQTT config chung cho toàn ứng dụng",
    )

    # Khác
    reminder: ReminderSettings = Field(default_factory=ReminderSettings)
    openmemory: OpenMemorySettings = Field(default_factory=OpenMemorySettings)
    read_config_from_api: bool = False
    mcp_endpoint: Optional[str] = None
    exit_commands: list = Field(default_factory=list)
    close_connection_no_voice_time: int = 120
    prompt: Optional[str] = None
    delete_audio: bool = True

    # Raw config dict (để giữ backward compatibility)
    _raw_config: Dict[str, Any] = {}

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "server": {
                    "ip": "0.0.0.0",
                    "port": 8003,
                    "http_port": 8003,
                },
                "selected_module": {
                    "VAD": "VAD_silero",
                    "ASR": "ASR_sherpa",
                    "LLM": "LLM_openai",
                },
            }
        },
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """Tạo Settings từ dict (để migrate từ YAML)"""
        reminder_data = data.get("reminder", {})

        # Parse MQTT config từ server.mqtt hoặc mqtt section
        mqtt_data = data.get("mqtt") or data.get("server", {}).get("mqtt")
        mqtt_config = MQTTSettings(**mqtt_data) if mqtt_data else None

        settings = cls(
            server=ServerSettings(**data.get("server", {})),
            auth=AuthSettings(**data.get("server", {}).get("auth", {})),
            selected_module=data.get("selected_module", {}),
            mqtt=mqtt_config,
            reminder=(
                ReminderSettings(**reminder_data)
                if isinstance(reminder_data, dict)
                else ReminderSettings()
            ),
            read_config_from_api=data.get("read_config_from_api", False),
            mcp_endpoint=data.get("mcp_endpoint"),
            exit_commands=data.get("exit_commands", []),
            close_connection_no_voice_time=data.get(
                "close_connection_no_voice_time", 120
            ),
            prompt=data.get("prompt"),
            delete_audio=data.get("delete_audio", True),
        )
        settings._raw_config = deepcopy(data)
        settings._raw_config.setdefault("reminder", settings.reminder.model_dump())
        return settings

    def to_dict(self) -> Dict[str, Any]:
        """Convert về dict (backward compatibility)"""
        return self._raw_config or self.model_dump()
