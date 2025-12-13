"""
Module Factory - Single source of truth cho việc khởi tạo các AI modules
Gộp logic từ modules_initialize.py, agent_module_initializer.py, module_initializer.py

Cấu trúc:
- Section 1: Core factory functions (initialize_tts, asr, vad, llm, memory, intent, voiceprint)
- Section 2: Module loaders
- Section 3: Async utilities
"""

import re
from typing import Any, Dict, Optional, Tuple

from app.core.logger import setup_logging
from app.ai.utils import asr, intent, llm, memory, tts, vad

TAG = __name__
logger = setup_logging()

# UUID regex pattern for validation
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ============================================================================
# SECTION 0: PROVIDER REFERENCE UTILITIES
# ============================================================================


def is_valid_uuid(value: str) -> bool:
    """Check if string is a valid UUID format."""
    return bool(UUID_PATTERN.match(value))


def parse_provider_reference(ref: str | None) -> Tuple[str, str] | None:
    """
    Parse provider reference string into (source, value) tuple.

    Args:
        ref: Provider reference string

    Returns:
        Tuple of (source, value) where source is "config" or "db", or None if ref is None

    Examples:
        >>> parse_provider_reference("config:CopilotLLM")
        ("config", "CopilotLLM")
        >>> parse_provider_reference("db:019abc-def")
        ("db", "019abc-def")
        >>> parse_provider_reference("019abc-def")  # plain UUID
        ("db", "019abc-def")
        >>> parse_provider_reference(None)
        None
    """
    if ref is None:
        return None

    if ref.startswith("config:"):
        return ("config", ref[7:])

    if ref.startswith("db:"):
        return ("db", ref[3:])

    # Backward compat: plain UUID -> treat as db reference
    if is_valid_uuid(ref):
        return ("db", ref)

    # Invalid format
    return None


def normalize_provider_reference(ref: str | None) -> str | None:
    """
    Normalize provider reference to standard format.

    - Plain UUID → "db:{uuid}"
    - "config:{name}" → unchanged
    - "db:{uuid}" → unchanged
    - None → None

    Args:
        ref: Provider reference string

    Returns:
        Normalized reference string

    Raises:
        ValueError: If reference format is invalid
    """
    if ref is None:
        return None

    # Already normalized formats
    if ref.startswith("config:"):
        name = ref[7:]
        if not name:
            raise ValueError("Config provider name cannot be empty")
        return ref

    if ref.startswith("db:"):
        uuid_part = ref[3:]
        if not is_valid_uuid(uuid_part):
            raise ValueError(f"Invalid provider UUID: {uuid_part}")
        return ref

    # Plain UUID -> normalize to db:{uuid}
    if is_valid_uuid(ref):
        return f"db:{ref}"

    raise ValueError(
        f"Invalid provider reference format: {ref}. "
        "Use 'config:{{name}}' or 'db:{{uuid}}' or plain UUID"
    )


def resolve_provider_reference(
    ref: str | None,
    category: str,
    config: Dict[str, Any],
    user_providers: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Resolve provider reference to provider config dict.

    Args:
        ref: Provider reference (e.g., "config:CopilotLLM", "db:uuid", or None)
        category: Provider category (LLM, TTS, ASR, etc.)
        config: App config dict containing provider definitions
        user_providers: Dict of user's DB providers keyed by category
            Format: {"LLM": {"type": "openai", "config": {...}}, ...}

    Returns:
        Provider config dict with "type" field, or None if not resolved

    Examples:
        >>> resolve_provider_reference("config:CopilotLLM", "LLM", config)
        {"type": "openai", "model_name": "gpt-4", ...}
        >>> resolve_provider_reference(None, "LLM", config)  # fallback
        {"type": "openai", ...}  # from selected_module
    """
    parsed = parse_provider_reference(ref)

    if parsed is None:
        # Fallback to selected_module
        selected_name = config.get("selected_module", {}).get(category)
        if selected_name and category in config and selected_name in config[category]:
            provider_config = config[category][selected_name]
            logger.bind(tag=TAG).debug(
                f"[{category}] Resolved from selected_module (fallback): {selected_name}"
            )
            return {
                **provider_config,
                "type": provider_config.get("type", selected_name),
            }
        return None

    source, value = parsed

    if source == "config":
        # Resolve from config.yml
        if category not in config:
            logger.bind(tag=TAG).warning(f"Category '{category}' not found in config")
            return None

        if value not in config[category]:
            logger.bind(tag=TAG).warning(
                f"Provider '{value}' not found in config[{category}]"
            )
            return None

        provider_config = config[category][value]
        provider_type = provider_config.get("type", value)
        logger.bind(tag=TAG).debug(
            f"[{category}] ✅ Resolved from CONFIG.YML: name={value}, type={provider_type}"
        )
        return {
            **provider_config,
            "type": provider_type,
        }

    elif source == "db":
        # Resolve from user_providers dict
        if not user_providers:
            logger.bind(tag=TAG).warning(
                f"No user_providers provided to resolve db:{value}"
            )
            return None

        # user_providers format: {"LLM": {"type": "...", "config": {...}}, ...}
        provider_data = user_providers.get(category)
        if not provider_data:
            logger.bind(tag=TAG).warning(
                f"No provider found for category '{category}' in user_providers"
            )
            return None

        # Return provider config with type
        provider_config = provider_data.get("config", {})
        provider_type = provider_data.get("type")
        provider_name = provider_data.get("name", value)
        logger.bind(tag=TAG).debug(
            f"[{category}] ✅ Resolved from DATABASE: id={value}, name={provider_name}, type={provider_type}"
        )
        return {
            **provider_config,
            "type": provider_type,
        }

    return None


# ============================================================================
# SECTION 1: CORE FACTORY FUNCTIONS
# ============================================================================


def initialize_tts(
    tts_module_name_or_config: Any,
    config: Optional[Dict[str, Any]] = None,
    delete_audio: Optional[bool] = None,
) -> Any:
    """
    Khởi tạo TTS module

    Backward compatible với cả 2 cách gọi:
    1. initialize_tts(config) - legacy
    2. initialize_tts(tts_module_name, config) - new

    Args:
        tts_module_name_or_config: Tên module TTS, hoặc config dict (backward compat)
        config: Config dict (None nếu param đầu là config)
        delete_audio: Override delete_audio setting, None = lấy từ config

    Returns:
        TTS instance
    """
    # Backward compatibility: nếu param đầu là dict và config là None -> legacy call
    if isinstance(tts_module_name_or_config, dict) and config is None:
        config = tts_module_name_or_config
        tts_module_name = config.get("selected_module", {}).get("TTS")
    else:
        tts_module_name = tts_module_name_or_config

    # Nếu tts_module_name là None, lấy từ selected_module
    if tts_module_name is None:
        tts_module_name = config.get("selected_module", {}).get("TTS")

    if not tts_module_name or tts_module_name not in config.get("TTS", {}):
        return None

    tts_config = config["TTS"][tts_module_name]
    tts_type = tts_module_name if "type" not in tts_config else tts_config["type"]

    # Xác định delete_audio flag
    if delete_audio is None:
        delete_audio = str(config.get("delete_audio", True)).lower() in (
            "true",
            "1",
            "yes",
        )

    new_tts = tts.create_instance(tts_type, tts_config, delete_audio)
    return new_tts


def initialize_asr(
    asr_module_name_or_config: Any,
    config: Optional[Dict[str, Any]] = None,
    delete_audio: Optional[bool] = None,
) -> Any:
    """
    Khởi tạo ASR module

    Backward compatible với cả 2 cách gọi:
    1. initialize_asr(config) - legacy
    2. initialize_asr(asr_module_name, config) - new

    Args:
        asr_module_name_or_config: Tên module ASR, hoặc config dict (backward compat)
        config: Config dict (None nếu param đầu là config)
        delete_audio: Override delete_audio setting, None = lấy từ config

    Returns:
        ASR instance
    """
    # Backward compatibility: nếu param đầu là dict và config là None -> legacy call
    if isinstance(asr_module_name_or_config, dict) and config is None:
        config = asr_module_name_or_config
        asr_module_name = config.get("selected_module", {}).get("ASR")
    else:
        asr_module_name = asr_module_name_or_config

    # Nếu asr_module_name là None, lấy từ selected_module
    if asr_module_name is None:
        asr_module_name = config.get("selected_module", {}).get("ASR")

    if not asr_module_name or asr_module_name not in config.get("ASR", {}):
        return None

    asr_config = config["ASR"][asr_module_name]
    asr_type = asr_module_name if "type" not in asr_config else asr_config["type"]

    # Xác định delete_audio flag
    if delete_audio is None:
        delete_audio = str(config.get("delete_audio", True)).lower() in (
            "true",
            "1",
            "yes",
        )

    new_asr = asr.create_instance(asr_type, asr_config, delete_audio)
    return new_asr


def initialize_vad(vad_module_name: str, config: Dict[str, Any]) -> Any:
    """
    Khởi tạo VAD module

    Args:
        vad_module_name: Tên module VAD (hoặc lấy từ config["selected_module"]["VAD"])
        config: Config dict

    Returns:
        VAD instance
    """
    # Nếu vad_module_name là None, lấy từ selected_module
    if vad_module_name is None:
        vad_module_name = config.get("selected_module", {}).get("VAD")

    if not vad_module_name or vad_module_name not in config.get("VAD", {}):
        return None

    vad_config = config["VAD"][vad_module_name]
    vad_type = vad_module_name if "type" not in vad_config else vad_config["type"]
    new_vad = vad.create_instance(vad_type, vad_config)
    return new_vad


def initialize_llm(llm_module_name: str, config: Dict[str, Any]) -> Any:
    """
    Khởi tạo LLM module

    Args:
        llm_module_name: Tên module LLM (hoặc lấy từ config["selected_module"]["LLM"])
        config: Config dict

    Returns:
        LLM instance
    """
    # Nếu llm_module_name là None, lấy từ selected_module
    if llm_module_name is None:
        llm_module_name = config.get("selected_module", {}).get("LLM")

    if not llm_module_name or llm_module_name not in config.get("LLM", {}):
        return None

    llm_config = config["LLM"][llm_module_name]
    llm_type = llm_module_name if "type" not in llm_config else llm_config["type"]
    new_llm = llm.create_instance(llm_type, llm_config)
    return new_llm


def initialize_memory(
    memory_module_name: str,
    config: Dict[str, Any],
    summary_memory: Optional[str] = None,
) -> Any:
    """
    Khởi tạo Memory module

    Args:
        memory_module_name: Tên module Memory (hoặc lấy từ config["selected_module"]["Memory"])
        config: Config dict
        summary_memory: Override summaryMemory setting

    Returns:
        Memory instance
    """
    # Nếu memory_module_name là None, lấy từ selected_module
    if memory_module_name is None:
        memory_module_name = config.get("selected_module", {}).get("Memory")

    if not memory_module_name or memory_module_name not in config.get("Memory", {}):
        return None

    memory_config = config["Memory"][memory_module_name]
    memory_type = (
        memory_module_name if "type" not in memory_config else memory_config["type"]
    )

    # Ưu tiên summary_memory từ param, fallback về config
    if summary_memory is None:
        summary_memory = config.get("summaryMemory", None)

    new_memory = memory.create_instance(memory_type, memory_config, summary_memory)
    return new_memory


def initialize_intent(intent_module_name: str, config: Dict[str, Any]) -> Any:
    """
    Khởi tạo Intent module

    Args:
        intent_module_name: Tên module Intent (hoặc lấy từ config["selected_module"]["Intent"])
        config: Config dict

    Returns:
        Intent instance
    """
    # Nếu intent_module_name là None, lấy từ selected_module
    if intent_module_name is None:
        intent_module_name = config.get("selected_module", {}).get("Intent")

    if not intent_module_name or intent_module_name not in config.get("Intent", {}):
        return None

    intent_config = config["Intent"][intent_module_name]
    intent_type = (
        intent_module_name if "type" not in intent_config else intent_config["type"]
    )
    new_intent = intent.create_instance(intent_type, intent_config)
    return new_intent


def initialize_voiceprint(asr_instance: Any, config: Dict[str, Any]) -> bool:
    """
    Khởi tạo chức năng nhận dạng giọng nói cho ASR instance

    Args:
        asr_instance: ASR instance đã được khởi tạo
        config: Config dict chứa voiceprint config

    Returns:
        bool: True nếu khởi tạo thành công, False nếu thất bại
    """
    voiceprint_config = config.get("voiceprint")
    if not voiceprint_config:
        return False

    # Kiểm tra cấu hình đầy đủ
    if not voiceprint_config.get("url") or not voiceprint_config.get("speakers"):
        logger.bind(tag=TAG).warning("Cấu hình nhận dạng giọng nói chưa đầy đủ")
        return False

    try:
        asr_instance.init_voiceprint(voiceprint_config)
        logger.bind(tag=TAG).info("Đã bật chức năng nhận dạng giọng nói của mô-đun ASR")
        logger.bind(tag=TAG).info(
            f"Số lượng người nói được cấu hình: {len(voiceprint_config['speakers'])}"
        )
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(
            f"Khởi tạo chức năng nhận dạng giọng nói thất bại: {str(e)}"
        )
        return False


# ============================================================================
# SECTION 1b: DIRECT CONFIG FACTORY FUNCTIONS (for DB providers)
# ============================================================================


def initialize_llm_from_config(provider_config: Dict[str, Any]) -> Any:
    """
    Khởi tạo LLM từ provider config dict (từ DB hoặc API request).

    Args:
        provider_config: Config dict có chứa "type" và các fields khác
            Example: {"type": "openai", "model_name": "gpt-4", "api_key": "..."}

    Returns:
        LLM instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    llm_type = provider_config.get("type")
    if not llm_type:
        raise ValueError("Provider config must have 'type' field")

    return llm.create_instance(llm_type, provider_config)


def initialize_tts_from_config(
    provider_config: Dict[str, Any],
    delete_audio: bool = True,
) -> Any:
    """
    Khởi tạo TTS từ provider config dict (từ DB hoặc API request).

    Args:
        provider_config: Config dict có chứa "type" và các fields khác
            Example: {"type": "edge", "voice": "vi-VN-HoaiMyNeural"}
        delete_audio: Có xóa file audio sau khi dùng không

    Returns:
        TTS instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    tts_type = provider_config.get("type")
    if not tts_type:
        raise ValueError("Provider config must have 'type' field")

    return tts.create_instance(tts_type, provider_config, delete_audio)


def initialize_asr_from_config(
    provider_config: Dict[str, Any],
    delete_audio: bool = True,
) -> Any:
    """
    Khởi tạo ASR từ provider config dict (từ DB hoặc API request).

    Args:
        provider_config: Config dict có chứa "type" và các fields khác
            Example: {"type": "openai", "api_key": "...", "model_name": "whisper-1"}
        delete_audio: Có xóa file audio sau khi dùng không

    Returns:
        ASR instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    asr_type = provider_config.get("type")
    if not asr_type:
        raise ValueError("Provider config must have 'type' field")

    return asr.create_instance(asr_type, provider_config, delete_audio)


def initialize_vad_from_config(provider_config: Dict[str, Any]) -> Any:
    """
    Khởi tạo VAD từ provider config dict.

    Args:
        provider_config: Config dict có chứa "type" và các fields khác

    Returns:
        VAD instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    vad_type = provider_config.get("type")
    if not vad_type:
        raise ValueError("Provider config must have 'type' field")

    return vad.create_instance(vad_type, provider_config)


def initialize_memory_from_config(
    provider_config: Dict[str, Any],
    summary_memory: Optional[str] = None,
) -> Any:
    """
    Khởi tạo Memory từ provider config dict.

    Args:
        provider_config: Config dict có chứa "type" và các fields khác
        summary_memory: Summary memory override

    Returns:
        Memory instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    memory_type = provider_config.get("type")
    if not memory_type:
        raise ValueError("Provider config must have 'type' field")

    return memory.create_instance(memory_type, provider_config, summary_memory)


def initialize_intent_from_config(provider_config: Dict[str, Any]) -> Any:
    """
    Khởi tạo Intent từ provider config dict.

    Args:
        provider_config: Config dict có chứa "type" và các fields khác

    Returns:
        Intent instance

    Raises:
        ValueError: Nếu thiếu "type" field
    """
    intent_type = provider_config.get("type")
    if not intent_type:
        raise ValueError("Provider config must have 'type' field")

    return intent.create_instance(intent_type, provider_config)


# ============================================================================
# SECTION 2: MODULE LOADERS
# ============================================================================


def load_modules_from_selected(
    config: Dict[str, Any],
    logger_instance=None,
    init_vad: bool = False,
    init_asr: bool = False,
    init_llm: bool = False,
    init_tts: bool = False,
    init_memory: bool = False,
    init_intent: bool = False,
) -> Dict[str, Any]:
    """
    Khởi tạo modules từ config["selected_module"]

    Args:
        config: Config dict
        logger_instance: Logger instance (optional)
        init_vad: Có khởi tạo VAD không
        init_asr: Có khởi tạo ASR không
        init_llm: Có khởi tạo LLM không
        init_tts: Có khởi tạo TTS không
        init_memory: Có khởi tạo Memory không
        init_intent: Có khởi tạo Intent không

    Returns:
        Dict[str, Any]: Dict chứa các module đã khởi tạo
    """
    log = logger_instance or logger
    modules = {}
    selected_module = config.get("selected_module", {})

    # Khởi tạo TTS
    if init_tts and "TTS" in selected_module:
        tts_name = selected_module["TTS"]
        if tts_name in config.get("TTS", {}):
            modules["tts"] = initialize_tts(tts_name, config)
            log.bind(tag=TAG).info(f"Khởi tạo thành phần: tts thành công {tts_name}")
        else:
            log.bind(tag=TAG).warning("TTS config không tồn tại, bỏ qua khởi tạo")

    # Khởi tạo ASR
    if init_asr and "ASR" in selected_module:
        asr_name = selected_module["ASR"]
        if asr_name in config.get("ASR", {}):
            modules["asr"] = initialize_asr(asr_name, config)
            log.bind(tag=TAG).info(f"Khởi tạo thành phần: asr thành công {asr_name}")
        else:
            log.bind(tag=TAG).warning("ASR config không tồn tại, bỏ qua khởi tạo")

    # Khởi tạo VAD
    if init_vad and "VAD" in selected_module:
        vad_name = selected_module["VAD"]
        if vad_name in config.get("VAD", {}):
            modules["vad"] = initialize_vad(vad_name, config)
            log.bind(tag=TAG).info(f"Khởi tạo thành phần: vad thành công {vad_name}")
        else:
            log.bind(tag=TAG).warning("VAD config không tồn tại, bỏ qua khởi tạo")

    # Khởi tạo LLM
    if init_llm and "LLM" in selected_module:
        llm_name = selected_module["LLM"]
        if llm_name in config.get("LLM", {}):
            modules["llm"] = initialize_llm(llm_name, config)
            log.bind(tag=TAG).info(f"Khởi tạo thành phần: llm thành công {llm_name}")
        else:
            log.bind(tag=TAG).warning("LLM config không tồn tại, bỏ qua khởi tạo")

    # Khởi tạo Memory
    if init_memory and "Memory" in selected_module:
        memory_name = selected_module["Memory"]
        if memory_name in config.get("Memory", {}):
            modules["memory"] = initialize_memory(memory_name, config)
            log.bind(tag=TAG).info(
                f"Khởi tạo thành phần: memory thành công {memory_name}"
            )
        else:
            log.bind(tag=TAG).warning("Memory config không tồn tại, bỏ qua khởi tạo")

    # Khởi tạo Intent
    if init_intent and "Intent" in selected_module:
        intent_name = selected_module["Intent"]
        if intent_name in config.get("Intent", {}):
            modules["intent"] = initialize_intent(intent_name, config)
            log.bind(tag=TAG).info(
                f"Khởi tạo thành phần: intent thành công {intent_name}"
            )
        else:
            log.bind(tag=TAG).warning("Intent config không tồn tại, bỏ qua khởi tạo")

    return modules


def _resolve_and_init_module(
    category: str,
    reference: str | None,
    config: Dict[str, Any],
    user_providers: Dict[str, Any] | None,
    delete_audio: bool,
    log,
) -> Any:
    """
    Resolve provider reference và khởi tạo module.

    Hỗ trợ format:
    - "config:{name}" - từ config.yml
    - "db:{uuid}" - từ user_providers dict
    - None - fallback selected_module

    Args:
        category: Module category (LLM, TTS, ASR, etc.)
        reference: Provider reference string hoặc None
        config: Full config dict
        user_providers: User providers dict từ DB query
        delete_audio: Flag delete audio sau khi dùng
        log: Logger instance

    Returns:
        Module instance hoặc None
    """
    log.bind(tag=TAG).debug(f"[{category}] Resolving reference: {reference}")

    # Resolve provider config từ reference
    provider_config = resolve_provider_reference(
        ref=reference,
        category=category,
        config=config,
        user_providers=user_providers,
    )

    if not provider_config:
        log.bind(tag=TAG).debug(f"[{category}] No provider config resolved")
        return None

    provider_type = provider_config.get("type")
    if not provider_type:
        log.bind(tag=TAG).warning(f"Provider config missing 'type' for {category}")
        return None

    # Initialize based on category
    try:
        module = None
        if category == "LLM":
            module = initialize_llm_from_config(provider_config)
        elif category == "TTS":
            module = initialize_tts_from_config(provider_config, delete_audio)
        elif category == "ASR":
            module = initialize_asr_from_config(provider_config, delete_audio)
        elif category == "VAD":
            module = initialize_vad_from_config(provider_config)
        elif category == "Memory":
            module = initialize_memory_from_config(provider_config)
        elif category == "Intent":
            module = initialize_intent_from_config(provider_config)

        if module:
            log.bind(tag=TAG).info(
                f"[{category}] ✅ Module initialized: type={provider_type}"
            )
        return module
    except Exception as e:
        log.bind(tag=TAG).error(f"Failed to init {category} from reference: {e}")
        return None

    return None


def load_modules_from_agent(
    config: Dict[str, Any],
    agent: Dict[str, Any],
    logger_instance=None,
    user_providers: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Khởi tạo modules từ agent config với provider reference support.

    Hỗ trợ cả:
    - Legacy: agent[category] = "module_name" (từ config.yml)
    - New: agent[category] = "config:{name}" hoặc "db:{uuid}"

    Args:
        config: Config dict
        agent: Agent config dict (chứa TTS, ASR, VAD, LLM, Memory, Intent keys)
        logger_instance: Logger instance (optional)
        user_providers: User providers dict từ DB (optional, for db: references)

    Returns:
        Dict[str, Any]: Dict chứa các module đã khởi tạo
    """
    log = logger_instance or logger
    modules = {}
    selected_module = config.get("selected_module", {})

    # Determine delete_audio flag
    delete_audio = str(config.get("delete_audio", True)).lower() in (
        "true",
        "1",
        "yes",
    )

    categories = ["TTS", "ASR", "VAD", "LLM", "Memory", "Intent"]

    log.bind(tag=TAG).debug(
        f"load_modules_from_agent: user_providers={'present' if user_providers else 'None'}"
    )

    for category in categories:
        agent_ref = agent.get(category)

        if agent_ref is None:
            continue

        # Check if it's a provider reference format
        parsed = parse_provider_reference(agent_ref)

        log.bind(tag=TAG).debug(f"[{category}] agent_ref={agent_ref}, parsed={parsed}")

        if parsed is not None:
            source, value = parsed
            # New format: config:{name} or db:{uuid}
            log.bind(tag=TAG).debug(
                f"[{category}] Using provider reference format: source={source}, value={value}"
            )
            module = _resolve_and_init_module(
                category=category,
                reference=agent_ref,
                config=config,
                user_providers=user_providers,
                delete_audio=delete_audio,
                log=log,
            )
            if module:
                modules[category.lower()] = module
                log.bind(tag=TAG).info(
                    f"[{category}] ✅ Loaded from {source.upper()}: {agent_ref}"
                )
        else:
            # Legacy format: module_name (từ config.yml)
            selected = selected_module.get(category)
            if (
                agent_ref
                and agent_ref != selected
                and agent_ref in config.get(category, {})
            ):
                log.bind(tag=TAG).debug(
                    f"[{category}] Using LEGACY format (module_name): {agent_ref}"
                )
                if category == "TTS":
                    modules["tts"] = initialize_tts(agent_ref, config)
                elif category == "ASR":
                    modules["asr"] = initialize_asr(agent_ref, config)
                elif category == "VAD":
                    modules["vad"] = initialize_vad(agent_ref, config)
                elif category == "LLM":
                    modules["llm"] = initialize_llm(agent_ref, config)
                elif category == "Memory":
                    modules["memory"] = initialize_memory(agent_ref, config)
                elif category == "Intent":
                    modules["intent"] = initialize_intent(agent_ref, config)

                if category.lower() in modules:
                    log.bind(tag=TAG).info(
                        f"[{category}] ✅ Loaded from CONFIG.YML (legacy): {agent_ref}"
                    )

    # Khởi tạo voiceprint nếu ASR module được khởi tạo
    if "asr" in modules and agent.get("voiceprint"):
        voiceprint_enabled = initialize_voiceprint(modules["asr"], config)
        if voiceprint_enabled:
            log.bind(tag=TAG).info("Khởi tạo voiceprint thành công")

    log.bind(tag=TAG).info(f"load_modules_from_agent completed: {list(modules.keys())}")
    return modules


def load_modules_from_providers(
    providers: Dict[str, Any],
    config: Dict[str, Any],
    logger_instance=None,
    summary_memory: Optional[str] = None,
    agent_template: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Khởi tạo modules từ provider configs (từ database).

    Ưu tiên dùng provider config từ DB, sau đó resolve config: references từ template,
    cuối cùng fallback về config.yml selected_module nếu provider NULL.

    Args:
        providers: Dict provider configs từ crud_agent.get_agent_by_mac_address()
            Format: {
                "ASR": {"type": "sherpa", "config": {...}} or None,
                "LLM": {"type": "openai", "config": {...}} or None,
                ...
            }
        config: Config dict (fallback khi provider NULL)
        logger_instance: Logger instance (optional)
        summary_memory: Override summaryMemory setting
        agent_template: Agent template dict với provider references (để resolve config:)

    Returns:
        Dict[str, Any]: Dict chứa các module đã khởi tạo
    """
    log = logger_instance or logger
    modules = {}
    selected_module = config.get("selected_module", {})

    log.bind(tag=TAG).debug(
        f"load_modules_from_providers: categories={list(providers.keys()) if providers else 'None'}"
    )

    # Determine delete_audio flag from config
    delete_audio = str(config.get("delete_audio", True)).lower() in (
        "true",
        "1",
        "yes",
    )

    # ASR
    asr_provider = providers.get("ASR")
    if asr_provider and asr_provider.get("config"):
        try:
            provider_config = {
                **asr_provider.get("config", {}),
                "type": asr_provider["type"],
            }
            modules["asr"] = initialize_asr_from_config(provider_config, delete_audio)
            log.bind(tag=TAG).info(
                f"[ASR] ✅ Loaded from DATABASE: name={asr_provider.get('name')}, type={asr_provider['type']}"
            )
        except Exception as e:
            log.bind(tag=TAG).error(f"[ASR] ❌ Failed to load from DB: {e}")
    elif agent_template and agent_template.get("ASR"):
        # Resolve config: reference from template
        asr_ref = agent_template.get("ASR")
        parsed = parse_provider_reference(asr_ref)
        if parsed:
            source, value = parsed
            if source == "config" and value in config.get("ASR", {}):
                modules["asr"] = initialize_asr(value, config)
                log.bind(tag=TAG).info(
                    f"[ASR] ✅ Loaded from CONFIG.YML (template): {value}"
                )
            elif source == "db":
                log.bind(tag=TAG).warning(
                    f"[ASR] DB reference {asr_ref} not found in providers, falling back"
                )
    elif selected_module.get("ASR"):
        # Fallback to config.yml selected_module
        asr_name = selected_module["ASR"]
        if asr_name in config.get("ASR", {}):
            modules["asr"] = initialize_asr(asr_name, config)
            log.bind(tag=TAG).info(
                f"[ASR] ✅ Loaded from CONFIG.YML (fallback): {asr_name}"
            )

    # LLM
    llm_provider = providers.get("LLM")
    if llm_provider and llm_provider.get("config"):
        try:
            provider_config = {
                **llm_provider.get("config", {}),
                "type": llm_provider["type"],
            }
            modules["llm"] = initialize_llm_from_config(provider_config)
            log.bind(tag=TAG).info(
                f"[LLM] ✅ Loaded from DATABASE: name={llm_provider.get('name')}, type={llm_provider['type']}"
            )
        except Exception as e:
            log.bind(tag=TAG).error(f"[LLM] ❌ Failed to load from DB: {e}")
    elif agent_template and agent_template.get("LLM"):
        # Resolve config: reference from template
        llm_ref = agent_template.get("LLM")
        parsed = parse_provider_reference(llm_ref)
        if parsed:
            source, value = parsed
            if source == "config" and value in config.get("LLM", {}):
                modules["llm"] = initialize_llm(value, config)
                log.bind(tag=TAG).info(
                    f"[LLM] ✅ Loaded from CONFIG.YML (template): {value}"
                )
            elif source == "db":
                log.bind(tag=TAG).warning(
                    f"[LLM] DB reference {llm_ref} not found in providers, falling back"
                )
    elif selected_module.get("LLM"):
        llm_name = selected_module["LLM"]
        if llm_name in config.get("LLM", {}):
            modules["llm"] = initialize_llm(llm_name, config)
            log.bind(tag=TAG).info(
                f"[LLM] ✅ Loaded from CONFIG.YML (fallback): {llm_name}"
            )

    # TTS
    tts_provider = providers.get("TTS")
    if tts_provider and tts_provider.get("config"):
        try:
            provider_config = {
                **tts_provider.get("config", {}),
                "type": tts_provider["type"],
            }
            modules["tts"] = initialize_tts_from_config(provider_config, delete_audio)
            log.bind(tag=TAG).info(
                f"[TTS] ✅ Loaded from DATABASE: name={tts_provider.get('name')}, type={tts_provider['type']}"
            )
        except Exception as e:
            log.bind(tag=TAG).error(f"[TTS] ❌ Failed to load from DB: {e}")
    elif agent_template and agent_template.get("TTS"):
        # Resolve config: reference from template
        tts_ref = agent_template.get("TTS")
        parsed = parse_provider_reference(tts_ref)
        if parsed:
            source, value = parsed
            if source == "config" and value in config.get("TTS", {}):
                modules["tts"] = initialize_tts(value, config)
                log.bind(tag=TAG).info(
                    f"[TTS] ✅ Loaded from CONFIG.YML (template): {value}"
                )
            elif source == "db":
                log.bind(tag=TAG).warning(
                    f"[TTS] DB reference {tts_ref} not found in providers, falling back"
                )
    elif selected_module.get("TTS"):
        tts_name = selected_module["TTS"]
        if tts_name in config.get("TTS", {}):
            modules["tts"] = initialize_tts(tts_name, config)
            log.bind(tag=TAG).info(
                f"[TTS] ✅ Loaded from CONFIG.YML (fallback): {tts_name}"
            )

    # Memory
    memory_provider = providers.get("Memory")
    if memory_provider and memory_provider.get("config"):
        try:
            provider_config = {
                **memory_provider.get("config", {}),
                "type": memory_provider["type"],
            }
            modules["memory"] = initialize_memory_from_config(
                provider_config, summary_memory
            )
            log.bind(tag=TAG).info(
                f"[Memory] ✅ Loaded from DATABASE: name={memory_provider.get('name')}, type={memory_provider['type']}"
            )
        except Exception as e:
            log.bind(tag=TAG).error(f"[Memory] ❌ Failed to load from DB: {e}")
    elif agent_template and agent_template.get("Memory"):
        # Resolve config: reference from template
        memory_ref = agent_template.get("Memory")
        parsed = parse_provider_reference(memory_ref)
        if parsed:
            source, value = parsed
            if source == "config" and value in config.get("Memory", {}):
                modules["memory"] = initialize_memory(value, config, summary_memory)
                log.bind(tag=TAG).info(
                    f"[Memory] ✅ Loaded from CONFIG.YML (template): {value}"
                )
            elif source == "db":
                log.bind(tag=TAG).warning(
                    f"[Memory] DB reference {memory_ref} not found in providers, falling back"
                )
    elif selected_module.get("Memory"):
        memory_name = selected_module["Memory"]
        if memory_name in config.get("Memory", {}):
            modules["memory"] = initialize_memory(memory_name, config, summary_memory)
            log.bind(tag=TAG).info(
                f"[Memory] ✅ Loaded from CONFIG.YML (fallback): {memory_name}"
            )

    # Intent
    intent_provider = providers.get("Intent")
    if intent_provider and intent_provider.get("config"):
        try:
            provider_config = {
                **intent_provider.get("config", {}),
                "type": intent_provider["type"],
            }
            modules["intent"] = initialize_intent_from_config(provider_config)
            log.bind(tag=TAG).info(
                f"[Intent] ✅ Loaded from DATABASE: name={intent_provider.get('name')}, type={intent_provider['type']}"
            )
        except Exception as e:
            log.bind(tag=TAG).error(f"[Intent] ❌ Failed to load from DB: {e}")
    elif agent_template and agent_template.get("Intent"):
        # Resolve config: reference from template
        intent_ref = agent_template.get("Intent")
        parsed = parse_provider_reference(intent_ref)
        if parsed:
            source, value = parsed
            if source == "config" and value in config.get("Intent", {}):
                modules["intent"] = initialize_intent(value, config)
                log.bind(tag=TAG).info(
                    f"[Intent] ✅ Loaded from CONFIG.YML (template): {value}"
                )
            elif source == "db":
                log.bind(tag=TAG).warning(
                    f"[Intent] DB reference {intent_ref} not found in providers, falling back"
                )
    elif selected_module.get("Intent"):
        intent_name = selected_module["Intent"]
        if intent_name in config.get("Intent", {}):
            modules["intent"] = initialize_intent(intent_name, config)
            log.bind(tag=TAG).info(
                f"[Intent] ✅ Loaded from CONFIG.YML (fallback): {intent_name}"
            )

    log.bind(tag=TAG).info(
        f"load_modules_from_providers completed: {list(modules.keys())}"
    )
    return modules


# ============================================================================
# SECTION 3: ASYNC UTILITIES
# ============================================================================


async def load_modules_async(
    thread_pool,
    config: Dict[str, Any],
    init_vad: bool = None,
    init_asr: bool = None,
    init_llm: bool = None,
    init_tts: bool = None,
    init_memory: bool = None,
    init_intent: bool = None,
) -> Dict[str, Any]:
    """
    Async wrapper để khởi tạo modules trong thread pool (không block event loop)

    Args:
        thread_pool: ThreadPoolService instance
        config: Config dict (hoặc Settings object)
        init_vad: Có khởi tạo VAD không (None = auto-detect từ selected_module)
        init_asr: Có khởi tạo ASR không (None = auto-detect từ selected_module)
        init_llm: Có khởi tạo LLM không (None = auto-detect từ selected_module)
        init_tts: Có khởi tạo TTS không (None = auto-detect từ selected_module)
        init_memory: Có khởi tạo Memory không (None = auto-detect từ selected_module)
        init_intent: Có khởi tạo Intent không (None = auto-detect từ selected_module)

    Returns:
        Dict[str, Any]: Dict chứa các module đã khởi tạo
    """

    def _init_modules_sync() -> Dict[str, Any]:
        """Sync initialization - chạy ở thread pool"""
        log = setup_logging()

        # Convert Settings object sang dict nếu cần
        config_dict = config
        if hasattr(config, "to_dict"):
            config_dict = config.to_dict()
        elif hasattr(config, "model_dump"):
            config_dict = config.model_dump()

        # Auto-detect from selected_module nếu flags là None
        selected_module = config_dict.get("selected_module", {})

        # Resolve init flags
        _init_vad = init_vad if init_vad is not None else ("VAD" in selected_module)
        _init_asr = init_asr if init_asr is not None else ("ASR" in selected_module)
        _init_llm = init_llm if init_llm is not None else ("LLM" in selected_module)
        _init_tts = init_tts if init_tts is not None else False  # TTS per-connection
        _init_memory = (
            init_memory if init_memory is not None else ("Memory" in selected_module)
        )
        _init_intent = (
            init_intent if init_intent is not None else ("Intent" in selected_module)
        )

        # Khởi tạo modules
        modules = load_modules_from_selected(
            config=config_dict,
            logger_instance=log,
            init_vad=_init_vad,
            init_asr=_init_asr,
            init_llm=_init_llm,
            init_tts=_init_tts,
            init_memory=_init_memory,
            init_intent=_init_intent,
        )

        log.bind(tag=TAG).info(f"Modules đã khởi tạo: {list(modules.keys())}")
        return modules

    # Chạy initialization ở thread pool không block
    return await thread_pool.run_blocking(_init_modules_sync)


# ============================================================================
# BACKWARD COMPATIBILITY (deprecated, sẽ remove sau)
# ============================================================================


# Alias cho main.py startup
initialize_modules = load_modules_async


def initialize_modules_sync(
    logger,
    config: Dict[str, Any],
    init_vad=False,
    init_asr=False,
    init_llm=False,
    init_tts=False,
    init_memory=False,
    init_intent=False,
) -> Dict[str, Any]:
    """
    DEPRECATED: Dùng load_modules_from_selected() thay thế
    Giữ lại để backward compatibility với code cũ
    """
    return load_modules_from_selected(
        config=config,
        logger_instance=logger,
        init_vad=init_vad,
        init_asr=init_asr,
        init_llm=init_llm,
        init_tts=init_tts,
        init_memory=init_memory,
        init_intent=init_intent,
    )


def initialize_modules_by_agent(
    logger,
    config: Dict[str, Any],
    agent: Dict[str, Any],
) -> Dict[str, Any]:
    """
    DEPRECATED: Dùng load_modules_from_agent() thay thế
    Giữ lại để backward compatibility với code cũ
    """
    return load_modules_from_agent(
        config=config,
        agent=agent,
        logger_instance=logger,
    )


def initialize_modules_by_selected_module(
    logger_instance,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    DEPRECATED: Dùng load_modules_from_selected() với all init flags = True
    Giữ lại để backward compatibility với code cũ
    """
    return load_modules_from_selected(
        config=config,
        logger_instance=logger_instance,
        init_vad=True,
        init_asr=True,
        init_llm=True,
        init_tts=True,
        init_memory=True,
        init_intent=True,
    )
