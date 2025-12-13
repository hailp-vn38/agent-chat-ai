"""Music tools: search, stream, stop."""

from .search_music import search_music
from .stream_music_url import stream_music_url
from .stop_music import stop_music
from .search_youtube import search_youtube
from .play_youtube import play_youtube

__all__ = [
    "search_music",
    "stream_music_url",
    "stop_music",
    "search_youtube",
    "play_youtube",
]

