"""Cấu hình logging cho Uvicorn sử dụng loguru."""

from loguru import logger


def setup_uvicorn_logging():
    """Cấu hình Uvicorn để sử dụng loguru thay vì logging mặc định."""
    import logging

    # Loại bỏ tất cả handlers mặc định của uvicorn
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_logger.propagate = False

    # Loại bỏ handlers của uvicorn.access
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False

    # Loại bỏ handlers của uvicorn.error
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.handlers = []
    error_logger.propagate = False

    # Custom handler để đẩy log từ logging tới loguru
    class InterceptHandler(logging.Handler):
        """Handler để bắt log từ logging module và gửi tới loguru."""

        def emit(self, record: logging.LogRecord) -> None:
            # Lấy level tương ứng
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Tìm caller
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            # Ghi log tới loguru
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Thêm handler tới uvicorn loggers
    uvicorn_logger.addHandler(InterceptHandler())
    access_logger.addHandler(InterceptHandler())
    error_logger.addHandler(InterceptHandler())

    # Thiết lập log level
    uvicorn_logger.setLevel(logging.INFO)
    access_logger.setLevel(logging.INFO)
    error_logger.setLevel(logging.INFO)
