"""
Component Initializer - Khởi tạo các thành phần (Memory, Intent, VAD, ASR, TTS, etc.)
"""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING
from app.core.logger import setup_logging
from app.ai.providers.tts.base import TTSProviderBase
from app.ai.providers.asr.base import ASRProviderBase

if TYPE_CHECKING:
    from app.ai.connection import (
        ConnectionHandler,
    )  # chỉ dùng cho hint, không chạy lúc runtime


TAG = __name__
logger = setup_logging()


def initialize_memory_component(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    logger_instance=None,
) -> bool:
    """
    Khởi tạo Memory component với logic chi tiết

    Args:
        conn: ConnectionHandler instance chứa memory instance
        config: Config dict
        logger_instance: Logger instance (optional)

    Returns:
        bool: True nếu khởi tạo thành công, False nếu không có memory hoặc lỗi
    """
    log = logger_instance or logger

    # Kiểm tra memory instance
    if conn.memory is None:
        log.bind(tag=TAG).debug("Memory instance không tồn tại, bỏ qua khởi tạo")
        return False

    try:
        # Bước 1: Khởi tạo memory cơ bản
        # Nếu có agent_id thì dùng, không thì dùng device_id
        role_id = conn.agent.get("id") or conn.device_id
        conn.memory.init_memory(
            role_id=role_id,
            llm=conn.llm,
            summary_memory=config.get("summaryMemory", None),
            save_to_file=not conn.read_config_from_api,
        )

        # Bước 2: Xác định loại memory
        memory_config = config.get("Memory", {})
        selected_memory_name = config.get("selected_module", {}).get("Memory")

        if not selected_memory_name or selected_memory_name not in memory_config:
            log.bind(tag=TAG).warning(
                f"Memory config không tồn tại cho: {selected_memory_name}"
            )
            return False

        memory_type = memory_config[selected_memory_name].get(
            "type", selected_memory_name
        )

        # Bước 3: Xử lý từng loại memory
        if memory_type == "nomem":
            log.bind(tag=TAG).debug("Memory type: nomem - không sử dụng memory")
            return True

        elif memory_type == "mem_local_short":
            return _setup_memory_llm(
                conn, config, memory_config, selected_memory_name, log
            )

        else:
            log.bind(tag=TAG).info(f"Memory type: {memory_type} - khởi tạo mặc định")
            return True

    except Exception as e:
        log.bind(tag=TAG).error(
            f"Lỗi khi khởi tạo Memory component: {str(e)}", exc_info=True
        )
        return False


def _setup_memory_llm(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    memory_config: Dict[str, Any],
    selected_memory_name: str,
    logger_instance,
) -> bool:
    """
    Thiết lập LLM riêng cho Memory nếu cần (loại mem_local_short)

    Args:
        conn: ConnectionHandler instance
        config: Config dict
        memory_config: Memory config dict
        selected_memory_name: Tên memory được chọn
        logger_instance: Logger instance

    Returns:
        bool: True nếu thành công
    """
    try:
        # Lấy tên LLM cho memory
        memory_llm_name = memory_config[selected_memory_name].get("llm")

        if not memory_llm_name:
            # Nếu không có llm riêng, dùng LLM chính
            conn.memory.set_llm(conn.llm)
            logger_instance.bind(tag=TAG).info(
                "Dùng LLM chính làm mô hình tóm tắt trí nhớ"
            )
            return True

        # Kiểm tra LLM có trong config không
        if memory_llm_name not in config.get("LLM", {}):
            logger_instance.bind(tag=TAG).warning(
                f"LLM '{memory_llm_name}' không tồn tại trong config, dùng LLM chính"
            )
            conn.memory.set_llm(conn.llm)
            return True

        # Tạo LLM riêng cho memory
        from app.ai.utils import llm as llm_utils

        memory_llm_config = config["LLM"][memory_llm_name]
        memory_llm_type = memory_llm_config.get("type", memory_llm_name)

        memory_llm = llm_utils.create_instance(memory_llm_type, memory_llm_config)

        conn.memory.set_llm(memory_llm)
        logger_instance.bind(tag=TAG).info(
            f"Tạo LLM riêng cho phần tóm tắt trí nhớ: {memory_llm_name}, loại: {memory_llm_type}"
        )
        return True

    except Exception as e:
        logger_instance.bind(tag=TAG).error(
            f"Lỗi khi thiết lập Memory LLM: {str(e)}", exc_info=True
        )
        # Fallback: dùng LLM chính
        try:
            conn.memory.set_llm(conn.llm)
            logger_instance.bind(tag=TAG).info(
                "Fallback: Dùng LLM chính làm mô hình tóm tắt trí nhớ"
            )
            return True
        except Exception as fallback_error:
            logger_instance.bind(tag=TAG).error(
                f"Fallback cũng thất bại: {str(fallback_error)}"
            )
            return False


def initialize_voiceprint_component(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    logger_instance=None,
) -> bool:
    """
    Khởi tạo Voiceprint component cho kết nối hiện tại

    Args:
        conn: ConnectionHandler instance
        config: Config dict
        logger_instance: Logger instance (optional)

    Returns:
        bool: True nếu khởi tạo thành công, False nếu lỗi hoặc voiceprint không được bật
    """
    log = logger_instance or logger

    try:
        # Lấy voiceprint config
        voiceprint_config = config.get("voiceprint", {})

        if not voiceprint_config:
            log.bind(tag=TAG).debug("Voiceprint chưa được bật")
            return False

        from app.ai.providers.voiceprints.voiceprint_provider import VoiceprintProvider

        # Khởi tạo voiceprint provider
        voiceprint_provider = VoiceprintProvider(voiceprint_config)

        # Kiểm tra xem provider có khả dụng không
        if voiceprint_provider is not None and voiceprint_provider.enabled:
            conn.voiceprint_provider = voiceprint_provider
            log.bind(tag=TAG).info("Voiceprint được kích hoạt động theo kết nối")
            return True
        else:
            log.bind(tag=TAG).warning("Voiceprint được bật nhưng cấu hình chưa đầy đủ")
            return False

    except Exception as e:
        log.bind(tag=TAG).warning(
            f"Khởi tạo voiceprint thất bại: {str(e)}", exc_info=True
        )
        return False


def initialize_asr_component(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    logger_instance=None,
) -> ASRProviderBase | None:
    """
    Khởi tạo ASR component

    Args:
        conn: ConnectionHandler instance
        config: Config dict
        logger_instance: Logger instance (optional)

    Returns:
        ASR instance hoặc None nếu lỗi
    """
    log = logger_instance or logger

    try:
        # Import các hàm cần thiết
        from app.ai.module_factory import initialize_asr
        from app.ai.providers.asr.dto.dto import InterfaceType

        # Kiểm tra ASR có khả dụng không
        if conn._asr is None:
            log.bind(tag=TAG).warning("_asr instance không tồn tại")
            return None

        # Nếu là local interface, dùng trực tiếp
        if conn._asr.interface_type == InterfaceType.LOCAL:
            log.bind(tag=TAG).debug("ASR tái sử dụng từ cache (LOCAL interface)")
            return conn._asr

        # Nếu không, khởi tạo từ config
        log.bind(tag=TAG).debug("Đang khởi tạo mô-đun ASR")
        asr = initialize_asr(config)

        if asr is not None:
            log.bind(tag=TAG).info("ASR khởi tạo thành công")
            return asr
        else:
            log.bind(tag=TAG).warning("Không thể khởi tạo ASR")
            return None

    except Exception as e:
        log.bind(tag=TAG).error(
            f"Lỗi khi khởi tạo ASR component: {str(e)}", exc_info=True
        )
        return None


def initialize_tts_component(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    logger_instance=None,
) -> TTSProviderBase | None:
    """
    Khởi tạo TTS component

    Args:
        conn: ConnectionHandler instance
        config: Config dict
        logger_instance: Logger instance (optional)

    Returns:
        TTS instance hoặc DefaultTTS nếu lỗi
    """
    log = logger_instance or logger

    try:
        # Import các hàm cần thiết
        from app.ai.module_factory import initialize_tts
        from app.ai.providers.tts.default import DefaultTTS

        log.bind(tag=TAG).debug("Đang khởi tạo mô-đun TTS")

        # Cố gắng khởi tạo TTS từ config
        tts = initialize_tts(config)

        # Nếu không thành công, dùng DefaultTTS
        if tts is None:
            log.bind(tag=TAG).debug("Sử dụng DefaultTTS thay thế")
            tts = DefaultTTS(config, delete_audio_file=True)

        if tts is not None:
            log.bind(tag=TAG).info("TTS khởi tạo thành công")
            return tts
        else:
            log.bind(tag=TAG).warning("Không thể khởi tạo TTS")
            return None

    except Exception as e:
        log.bind(tag=TAG).error(
            f"Lỗi khi khởi tạo TTS component: {str(e)}", exc_info=True
        )
        return None


def initialize_intent_component(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    logger_instance=None,
) -> bool:
    """
    Khởi tạo Intent component với logic chi tiết

    Args:
        conn: ConnectionHandler instance chứa intent instance
        config: Config dict
        logger_instance: Logger instance (optional)

    Returns:
        bool: True nếu khởi tạo thành công, False nếu không có intent hoặc lỗi
    """
    log = logger_instance or logger

    # Kiểm tra intent instance
    if conn.intent is None:
        log.bind(tag=TAG).debug("Intent instance không tồn tại, bỏ qua khởi tạo")
        return False

    try:
        # Bước 1: Xác định loại intent
        intent_config = config.get("Intent", {})
        selected_intent_name = config.get("selected_module", {}).get("Intent")

        if not selected_intent_name or selected_intent_name not in intent_config:
            log.bind(tag=TAG).warning(
                f"Intent config không tồn tại cho: {selected_intent_name}"
            )
            return False

        intent_type = intent_config[selected_intent_name].get(
            "type", selected_intent_name
        )

        # Bước 2: Set intent_type trên conn
        conn.intent_type = intent_type

        # Bước 3: Xác định xem có cần load function plugin không
        if intent_type == "function_call" or intent_type == "intent_llm":
            conn.load_function_plugin = True
            log.bind(tag=TAG).debug(
                f"Function plugin sẽ được load cho intent type: {intent_type}"
            )

        # Bước 4: Xử lý từng loại intent
        if intent_type == "nointent":
            log.bind(tag=TAG).debug("Intent type: nointent - không sử dụng intent")
            return True

        elif intent_type == "intent_llm":
            return _setup_intent_llm(
                conn, config, intent_config, selected_intent_name, log
            )

        else:
            log.bind(tag=TAG).info(f"Intent type: {intent_type} - khởi tạo mặc định")
            return True

    except Exception as e:
        log.bind(tag=TAG).error(
            f"Lỗi khi khởi tạo Intent component: {str(e)}", exc_info=True
        )
        return False


def _setup_intent_llm(
    conn: ConnectionHandler,
    config: Dict[str, Any],
    intent_config: Dict[str, Any],
    selected_intent_name: str,
    logger_instance,
) -> bool:
    """
    Thiết lập LLM riêng cho Intent nếu cần (loại intent_llm)

    Args:
        conn: ConnectionHandler instance
        config: Config dict
        intent_config: Intent config dict
        selected_intent_name: Tên intent được chọn
        logger_instance: Logger instance

    Returns:
        bool: True nếu thành công
    """
    try:
        # Lấy tên LLM cho intent
        intent_llm_name = intent_config[selected_intent_name].get("llm")

        if not intent_llm_name:
            # Nếu không có llm riêng, dùng LLM chính
            conn.intent.set_llm(conn.llm)
            logger_instance.bind(tag=TAG).info(
                "Dùng LLM chính làm mô hình nhận diện ý định"
            )
            return True

        # Kiểm tra LLM có trong config không
        if intent_llm_name not in config.get("LLM", {}):
            logger_instance.bind(tag=TAG).warning(
                f"LLM '{intent_llm_name}' không tồn tại trong config, dùng LLM chính"
            )
            conn.intent.set_llm(conn.llm)
            return True

        # Tạo LLM riêng cho intent
        from app.ai.utils import llm as llm_utils

        intent_llm_config = config["LLM"][intent_llm_name]
        intent_llm_type = intent_llm_config.get("type", intent_llm_name)

        intent_llm = llm_utils.create_instance(intent_llm_type, intent_llm_config)

        conn.intent.set_llm(intent_llm)
        logger_instance.bind(tag=TAG).info(
            f"Tạo LLM riêng cho ý định: {intent_llm_name}, loại: {intent_llm_type}"
        )
        return True

    except Exception as e:
        logger_instance.bind(tag=TAG).error(
            f"Lỗi khi thiết lập Intent LLM: {str(e)}", exc_info=True
        )
        # Fallback: dùng LLM chính
        try:
            conn.intent.set_llm(conn.llm)
            logger_instance.bind(tag=TAG).info(
                "Fallback: Dùng LLM chính làm mô hình nhận diện ý định"
            )
            return True
        except Exception as fallback_error:
            logger_instance.bind(tag=TAG).error(
                f"Fallback cũng thất bại: {str(fallback_error)}"
            )
            return False
