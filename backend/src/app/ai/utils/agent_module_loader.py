"""
Utility functions for loading and applying agent modules.

Handles the common logic of:
1. Loading modules from agent_info
2. Binding connection to modules
3. Updating config with module selections
4. Opening audio channels for modules that support it
"""

from typing import Dict, Any, Tuple, TYPE_CHECKING
import copy

if TYPE_CHECKING:
    from app.ai.connection import ConnectionHandler

# Module configuration map - defines behavior for each module type
MODULE_CONFIG_MAP = {
    "tts": {
        "attr_name": "tts",
        "config_key": "tts",
        "has_conn": True,
        "has_audio_channels": True,
    },
    "asr": {
        "attr_name": "asr",
        "config_key": "asr",
        "has_conn": True,
        "has_audio_channels": True,
    },
    "vad": {
        "attr_name": "vad",
        "config_key": "vad",
        "has_conn": True,
        "has_audio_channels": False,
    },
    "llm": {
        "attr_name": "llm",
        "config_key": "llm",
        "has_conn": True,
        "has_audio_channels": False,
    },
    "intent": {
        "attr_name": "intent",
        "config_key": "intent",
        "has_conn": True,
        "has_audio_channels": False,
    },
    "memory": {
        "attr_name": "memory",
        "config_key": "memory",
        "has_conn": True,
        "has_audio_channels": False,
    },
}


async def apply_agent_modules(
    agent_config: Dict[str, Any],
    conn: "ConnectionHandler",
    base_config: Dict[str, Any],
    modules_dict: Dict[str, Any],
    logger: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply loaded modules to connection and update config.

    Handles:
    - Binding connection to each module (if supported)
    - Opening audio channels (if supported)
    - Updating selected_module config

    Args:
        agent_config: Agent info dict containing module names (TTS, ASR, VAD, etc.)
        conn: ConnectionHandler instance to bind modules to
        base_config: Base config dict to update with selected modules
        modules_dict: Dict of loaded modules (keys: "tts", "asr", etc.)
        logger: Logger instance

    Returns:
        Tuple of (updated_config, old_modules_dict)
        - updated_config: Config with selected_module updated
        - old_modules_dict: Dict mapping attr_name -> old module (for rollback)
    """
    updated_config = copy.deepcopy(base_config)
    old_modules = {}

    # Ensure selected_module structure exists
    if "selected_module" not in updated_config:
        updated_config["selected_module"] = {}

    for module_key, module_config in MODULE_CONFIG_MAP.items():
        if module_key not in modules_dict or modules_dict[module_key] is None:
            continue

        new_module = modules_dict[module_key]
        attr_name = module_config["attr_name"]
        config_key = module_config["config_key"]
        has_conn = module_config["has_conn"]
        has_audio_channels = module_config["has_audio_channels"]

        # Save old module for potential rollback
        old_module = getattr(conn, attr_name, None)
        if old_module is not None:
            old_modules[attr_name] = old_module

        # Assign new module
        setattr(conn, attr_name, new_module)

        # Bind connection if module supports it
        if has_conn and hasattr(new_module, "conn"):
            new_module.conn = conn

        # Open audio channels if module supports it
        if has_audio_channels and hasattr(new_module, "open_audio_channels"):
            try:
                await new_module.open_audio_channels(conn)
                logger.bind(tag="AgentModuleLoader").debug(
                    f"Opened audio channels for {module_key}"
                )
            except Exception as e:
                logger.bind(tag="AgentModuleLoader").warning(
                    f"Failed to open audio channels for {module_key}: {e}"
                )

        # Update selected_module config
        if module_key.upper() in agent_config:
            updated_config["selected_module"][config_key] = agent_config.get(
                module_key.upper()
            )

    return updated_config, old_modules


def apply_agent_config_fields(
    agent_config: Dict[str, Any],
    base_config: Dict[str, Any],
    conn: "ConnectionHandler",
    logger: Any,
) -> Dict[str, Any]:
    """
    Apply agent config fields (prompt, voiceprint, etc.) to connection and config.

    Handles field mapping and type conversion.

    Args:
        agent_config: Agent info dict with fields to apply
        base_config: Base config dict to update
        conn: ConnectionHandler instance to update attributes
        logger: Logger instance

    Returns:
        Updated config dict with agent fields applied
    """
    updated_config = copy.deepcopy(base_config)

    # Field mappings: (agent_config_key, config_key, conn_attr, type_converter)
    field_mappings = [
        ("prompt", "prompt", None, None),
        ("voiceprint", "voiceprint", None, None),
        ("summaryMemory", "summaryMemory", None, None),
        ("device_max_output_size", None, "max_output_size", int),
        ("chat_history_conf", None, "chat_history_conf", int),
        ("mcp_endpoint", "mcp_endpoint", None, None),
    ]

    for agent_key, config_key, conn_attr, type_converter in field_mappings:
        if agent_config.get(agent_key) is None:
            continue

        value = agent_config[agent_key]

        # Apply to config if key exists
        if config_key:
            updated_config[config_key] = value

        # Apply to connection if attribute exists
        if conn_attr and hasattr(conn, conn_attr):
            if type_converter:
                try:
                    value = type_converter(value)
                except (ValueError, TypeError) as e:
                    logger.bind(tag="AgentModuleLoader").warning(
                        f"Failed to convert {agent_key}={value} to {type_converter.__name__}: {e}"
                    )
                    continue

            setattr(conn, conn_attr, value)

    return updated_config
