"""Audio streaming providers for URL-based music playback."""

from .ogg_opus_parser import OggOpusParser
from .ffmpeg_streamer import FFmpegURLStreamer

__all__ = ["OggOpusParser", "FFmpegURLStreamer"]

