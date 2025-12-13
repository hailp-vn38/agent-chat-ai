from enum import Enum


class TextMessageType(Enum):
    """Enum các loại thông điệp"""

    HELLO = "hello"
    ABORT = "abort"
    LISTEN = "listen"
    IOT = "iot"
    MCP = "mcp"
    SERVER = "server"
    REMINDER = "reminder"
    NOTIFICATION = "notification"
    SPEAK = "speak"
