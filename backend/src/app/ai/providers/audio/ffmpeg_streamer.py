"""
FFmpeg URL Streamer - Real-time audio streaming từ URL.

Sử dụng FFmpeg subprocess để:
1. Fetch audio từ HTTP URL
2. Transcode sang Opus format
3. Output Ogg/Opus container qua stdout
4. Parse Ogg để extract raw Opus frames
"""

from __future__ import annotations

import asyncio
import shutil
from typing import AsyncGenerator

from app.core.logger import setup_logging
from .ogg_opus_parser import OggOpusParser

TAG = __name__
logger = setup_logging()


class FFmpegURLStreamer:
    """Stream audio từ URL qua FFmpeg, output opus frames."""

    def __init__(self, url: str, frame_duration_ms: int = 60):
        """
        Initialize streamer.

        Args:
            url: HTTP/HTTPS URL của audio file
            frame_duration_ms: Opus frame duration (20, 40, 60ms)
        """
        self.url = url
        self.frame_duration_ms = frame_duration_ms
        self.process: asyncio.subprocess.Process | None = None
        self.stopped = False
        self._parser = OggOpusParser()

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Check if FFmpeg binary is available."""
        return shutil.which("ffmpeg") is not None

    async def stream_opus_frames(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator yielding opus frames.

        Yields:
            Raw Opus frame bytes (không có Ogg container)

        Raises:
            RuntimeError: If FFmpeg is not available
            Exception: If FFmpeg process fails
        """
        if not self.is_ffmpeg_available():
            logger.bind(tag=TAG).error("[stream_opus_frames] FFmpeg không được cài đặt")
            raise RuntimeError("FFmpeg is not installed")

        # FFmpeg command: URL input → Opus/Ogg stdout
        cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", self.url,
            "-vn",  # No video
            "-acodec", "libopus",
            "-ar", "16000",  # 16kHz sample rate cho voice
            "-ac", "1",  # Mono
            "-b:a", "24k",  # 24kbps bitrate
            "-frame_duration", str(self.frame_duration_ms),
            "-application", "audio",  # Optimize for music
            "-f", "ogg",  # Ogg container
            "-",  # Output to stdout
        ]

        logger.bind(tag=TAG).debug(f"[stream_opus_frames] FFmpeg command: {' '.join(cmd)}")
        logger.bind(tag=TAG).debug(f"[stream_opus_frames] URL: {self.url[:100]}...")

        try:
            logger.bind(tag=TAG).debug("[stream_opus_frames] Spawning FFmpeg subprocess...")
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            logger.bind(tag=TAG).debug(f"[stream_opus_frames] FFmpeg PID: {self.process.pid}")

            # Read stdout in chunks
            chunk_count = 0
            total_bytes_read = 0
            total_frames_parsed = 0

            while not self.stopped:
                if self.process.stdout is None:
                    logger.bind(tag=TAG).warning("[stream_opus_frames] stdout is None")
                    break

                chunk = await self.process.stdout.read(4096)
                if not chunk:
                    logger.bind(tag=TAG).debug("[stream_opus_frames] EOF reached")
                    break

                chunk_count += 1
                total_bytes_read += len(chunk)

                # Log first chunk và progress
                if chunk_count == 1:
                    logger.bind(tag=TAG).debug(
                        f"[stream_opus_frames] First chunk: {len(chunk)} bytes, "
                        f"header: {chunk[:20].hex()}"
                    )
                elif chunk_count % 50 == 0:
                    logger.bind(tag=TAG).debug(
                        f"[stream_opus_frames] Progress: {chunk_count} chunks, "
                        f"{total_bytes_read} bytes, {total_frames_parsed} frames"
                    )

                # Parse Ogg container và yield Opus frames
                frames = self._parser.feed(chunk)
                for frame in frames:
                    if self.stopped:
                        break
                    total_frames_parsed += 1
                    yield frame

            logger.bind(tag=TAG).debug(
                f"[stream_opus_frames] Loop ended: chunks={chunk_count}, "
                f"bytes={total_bytes_read}, frames={total_frames_parsed}, stopped={self.stopped}"
            )

            # Đọc stderr để debug nếu có lỗi
            if self.process.returncode is None:
                logger.bind(tag=TAG).debug("[stream_opus_frames] Waiting for FFmpeg to exit...")
                await self.process.wait()

            logger.bind(tag=TAG).debug(
                f"[stream_opus_frames] FFmpeg exit code: {self.process.returncode}"
            )

            if self.process.returncode != 0 and not self.stopped:
                stderr_data = await self.process.stderr.read() if self.process.stderr else b""
                stderr_text = stderr_data.decode("utf-8", errors="ignore")[-500:]
                logger.bind(tag=TAG).warning(
                    f"[stream_opus_frames] FFmpeg error (code {self.process.returncode}):\n{stderr_text}"
                )

        except asyncio.CancelledError:
            logger.bind(tag=TAG).debug("[stream_opus_frames] Cancelled")
            raise
        except Exception as e:
            logger.bind(tag=TAG).error(f"[stream_opus_frames] Exception: {e}", exc_info=True)
            raise
        finally:
            logger.bind(tag=TAG).debug("[stream_opus_frames] Running cleanup...")
            await self._cleanup()

    async def _cleanup(self):
        """Cleanup subprocess resources."""
        if self.process is None:
            return

        try:
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
        except ProcessLookupError:
            pass  # Process already dead
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Error during FFmpeg cleanup: {e}")
        finally:
            self.process = None
            self._parser.reset()

    def stop(self):
        """Stop streaming và terminate subprocess."""
        self.stopped = True
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass

    async def stop_async(self):
        """Async version of stop với proper cleanup."""
        self.stopped = True
        await self._cleanup()

