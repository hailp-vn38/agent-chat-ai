
"""
ThreadPool Service - Phương án B: Xử lý tránh block luồng
Dùng asyncio.to_thread() hoặc loop.run_in_executor()
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional, TypeVar
from functools import wraps

T = TypeVar("T")


class ThreadPoolService:
    """Service quản lý thread pool để xử lý blocking tasks"""

    def __init__(self, max_workers: int = 10):
        """
        Args:
            max_workers: Số worker threads
        """
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="server-thread-pool-"
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Lấy event loop hiện tại"""
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def run_blocking(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Chạy blocking function ở thread pool ko block main loop

        Args:
            func: Sync function cần chạy
            *args, **kwargs: Tham số của function

        Returns:
            Kết quả từ function

        Example:
            result = await thread_pool.run_blocking(
                heavy_asr_processing,
                audio_data,
                sample_rate=16000
            )
        """
        # Python 3.9+: asyncio.to_thread() đơn giản hơn
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except RuntimeError:
            # Fallback nếu ko có event loop
            return await self.loop.run_in_executor(
                self.executor, lambda: func(*args, **kwargs)
            )

    async def run_in_executor(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Chạy function ở thread pool (explicit executor)

        Dùng khi muốn kiểm soát tường minh executor
        """
        return await self.loop.run_in_executor(
            self.executor, lambda: func(*args, **kwargs)
        )

    async def run_and_stream(
        self, generator_func: Callable[..., Any], *args, chunk_size: int = 1, **kwargs
    ):
        """
        Chạy generator function ở thread pool và yield results

        Dùng cho streaming (audio chunks, LLM tokens, etc)

        Example:
            async for chunk in thread_pool.run_and_stream(
                asr_recognize,
                audio_data
            ):
                await websocket.send_bytes(chunk)
        """

        def wrapper():
            return generator_func(*args, **kwargs)

        # Chạy generator ở thread pool
        gen = await self.run_blocking(wrapper)

        # Stream kết quả
        chunk_buffer = []
        for item in gen:
            chunk_buffer.append(item)
            if len(chunk_buffer) >= chunk_size:
                yield chunk_buffer
                chunk_buffer = []

        # Yield phần còn lại
        if chunk_buffer:
            yield chunk_buffer

    def shutdown(self, wait: bool = True):
        """
        Tắt thread pool

        Args:
            wait: Chờ các task hoàn thành trước khi tắt
        """
        self.executor.shutdown(wait=wait)


class async_blocking:
    """
    Decorator để convert sync function thành async
    Dùng cho methods cần xử lý blocking

    Example:
        @async_blocking
        def process_audio(self, data):
            return self.asr.process(data)

        result = await obj.process_audio(data)
    """

    def __init__(self, thread_pool: ThreadPoolService):
        self.thread_pool = thread_pool

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.thread_pool.run_blocking(func, *args, **kwargs)

        return wrapper


def create_async_wrapper(thread_pool: ThreadPoolService, func: Callable) -> Callable:
    """
    Utility để tạo async wrapper cho sync function

    Example:
        async_asr = create_async_wrapper(thread_pool, connection.chat)
        result = await async_asr(query)
    """

    async def wrapper(*args, **kwargs):
        return await thread_pool.run_blocking(func, *args, **kwargs)

    return wrapper
