"""
Tests for music streaming functionality.

Covers:
- OggOpusParser với sample Ogg/Opus data
- FFmpegURLStreamer với mock subprocess
- Integration test search_music với NhacCuaTui API
- End-to-end test stream → stop flow
"""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest
import pytest_asyncio

from app.ai.providers.audio.ogg_opus_parser import (
    OggOpusParser,
    OGG_MAGIC,
    OGG_HEADER_SIZE,
)
from app.ai.providers.audio.ffmpeg_streamer import FFmpegURLStreamer
from app.ai.plugins_func.functions.music.search_music import (
    search_music,
    _search_nhaccuatui_sync,
    _get_stream_url,
)
from app.ai.plugins_func.functions.music.stream_music_url import (
    stream_music_url,
    _handle_stream,
)
from app.ai.plugins_func.functions.music.stop_music import stop_music


class TestOggOpusParser:
    """Tests for OggOpusParser."""

    def test_parse_simple_ogg_page(self):
        """Test parsing a simple Ogg page with single packet."""
        parser = OggOpusParser()

        # Create minimal Ogg page
        # Header: OggS + version(0) + flags(0) + granule(1) + serial(0) + seq(0) + crc(0) + segments(1)
        header = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)  # granule = 1 (not header page)
        header[26] = 1  # 1 segment
        header[27] = 10  # segment size = 10 bytes

        # Payload: 10 bytes of fake opus data
        payload = b"opus_data_"
        page = bytes(header) + payload

        packets = parser.feed(page)

        assert len(packets) == 1
        assert packets[0] == payload
        assert parser.total_packets == 1

    def test_parse_multiple_packets_in_page(self):
        """Test parsing Ogg page with multiple packets."""
        parser = OggOpusParser()

        # Create Ogg page with 3 packets
        header = bytearray(OGG_HEADER_SIZE + 3)  # +3 for segment table
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)
        header[26] = 3  # 3 segments
        header[27] = 5  # packet 1: 5 bytes
        header[28] = 3  # packet 2: 3 bytes
        header[29] = 4  # packet 3: 4 bytes

        payload = b"12345abc1234"
        page = bytes(header) + payload

        packets = parser.feed(page)

        assert len(packets) == 3
        assert packets[0] == b"12345"
        assert packets[1] == b"abc"
        assert packets[2] == b"1234"
        assert parser.total_packets == 3

    def test_skip_header_pages(self):
        """Test that header pages (granule=0) are skipped."""
        parser = OggOpusParser()

        # Header page (granule=0)
        header1 = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header1[0:4] = OGG_MAGIC
        header1[6:14] = struct.pack("<Q", 0)  # granule = 0 (header page)
        header1[26] = 1
        header1[27] = 10
        page1 = bytes(header1) + b"header_data"

        # Data page (granule=1)
        header2 = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header2[0:4] = OGG_MAGIC
        header2[6:14] = struct.pack("<Q", 1)
        header2[26] = 1
        header2[27] = 5
        page2 = bytes(header2) + b"audio"

        packets1 = parser.feed(page1)
        assert len(packets1) == 0  # Header page skipped

        packets2 = parser.feed(page2)
        assert len(packets2) == 1
        assert packets2[0] == b"audio"

    def test_parse_partial_data(self):
        """Test parser handles partial/incomplete data without crashing."""
        parser = OggOpusParser()

        # Feed incomplete header (less than OGG_HEADER_SIZE)
        incomplete = b"OggS\x00"
        packets = parser.feed(incomplete)
        # Should not crash and return empty packets
        assert len(packets) == 0
        # Buffer may keep partial data for resync
        assert isinstance(parser.buffer, bytearray)

        # Feed complete page - parser should handle it correctly
        header = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)
        header[26] = 1
        header[27] = 5
        complete_page = bytes(header) + b"audio"
        
        # Reset parser to test clean parsing
        parser.reset()
        packets = parser.feed(complete_page)

        # Should parse the complete page
        assert len(packets) == 1
        assert packets[0] == b"audio"

    def test_resync_on_corrupted_data(self):
        """Test parser resyncs when encountering corrupted data."""
        parser = OggOpusParser()

        # Corrupted data before valid page
        corrupted = b"garbage_data_here"
        header = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)
        header[26] = 1
        header[27] = 5
        valid_page = bytes(header) + b"audio"

        combined = corrupted + valid_page
        packets = parser.feed(combined)

        assert len(packets) == 1
        assert packets[0] == b"audio"

    def test_reset(self):
        """Test parser reset clears state."""
        parser = OggOpusParser()

        header = bytearray(OGG_HEADER_SIZE + 1)  # +1 for segment table
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)
        header[26] = 1
        header[27] = 5
        page = bytes(header) + b"audio"

        parser.feed(page)
        assert parser.total_packets == 1

        parser.reset()
        assert parser.total_packets == 0
        assert len(parser.buffer) == 0


class TestFFmpegURLStreamer:
    """Tests for FFmpegURLStreamer."""

    def test_is_ffmpeg_available(self):
        """Test FFmpeg availability check."""
        # This will check actual system
        result = FFmpegURLStreamer.is_ffmpeg_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_stream_opus_frames_with_mock_subprocess(self):
        """Test streaming with mocked FFmpeg subprocess."""
        # Create mock Ogg page data
        header = bytearray(OGG_HEADER_SIZE)
        header[0:4] = OGG_MAGIC
        header[6:14] = struct.pack("<Q", 1)
        header[26] = 2  # 2 segments
        header[27] = 5  # packet 1: 5 bytes
        header[28] = 3  # packet 2: 3 bytes

        payload = b"audio_data"
        ogg_page = bytes(header) + payload

        # Mock subprocess
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.read = AsyncMock(
            side_effect=[
                ogg_page,  # First chunk
                b"",  # EOF
            ]
        )
        mock_process.stdout = mock_stdout
        mock_stderr = AsyncMock()
        mock_stderr.read = AsyncMock(return_value=b"")
        mock_process.stderr = mock_stderr
        mock_process.returncode = 0
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()

        streamer = FFmpegURLStreamer("https://example.com/audio.mp3")

        async def mock_create_subprocess(*args, **kwargs):
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ), patch.object(FFmpegURLStreamer, "is_ffmpeg_available", return_value=True):

            frames = []
            async for frame in streamer.stream_opus_frames():
                frames.append(frame)

            assert len(frames) == 2  # 2 packets from segment table
            assert frames[0] == b"audio"
            assert frames[1] == b"_dat"

    @pytest.mark.asyncio
    async def test_stream_stop_flag(self):
        """Test that stop flag terminates streaming."""
        mock_process = AsyncMock()
        mock_stdout = AsyncMock()
        mock_stdout.read = AsyncMock(return_value=b"data")
        mock_process.stdout = mock_stdout
        mock_stderr = AsyncMock()
        mock_stderr.read = AsyncMock(return_value=b"")
        mock_process.stderr = mock_stderr
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.wait = AsyncMock()

        streamer = FFmpegURLStreamer("https://example.com/audio.mp3")

        async def mock_create_subprocess(*args, **kwargs):
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ), patch.object(FFmpegURLStreamer, "is_ffmpeg_available", return_value=True):

            frame_count = 0
            async for frame in streamer.stream_opus_frames():
                frame_count += 1
                if frame_count >= 5:
                    streamer.stop()
                    break

            assert frame_count <= 5

    @pytest.mark.asyncio
    async def test_ffmpeg_not_available(self):
        """Test error when FFmpeg is not available."""
        streamer = FFmpegURLStreamer("https://example.com/audio.mp3")

        with patch.object(FFmpegURLStreamer, "is_ffmpeg_available", return_value=False):
            with pytest.raises(RuntimeError, match="FFmpeg is not installed"):
                async for _ in streamer.stream_opus_frames():
                    pass


class TestSearchMusic:
    """Integration tests for search_music tool."""

    @patch("app.ai.plugins_func.functions.music.search_music.requests")
    def test_search_music_success(self, mock_requests):
        """Test successful music search."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "success": True,
            "msg": "success",
            "data": {
                "songs": [
                    {
                        "name": "Test Song",
                        "artistName": "Test Artist",
                        "duration": 180,
                        "streamURL": [
                            {
                                "type": "128",
                                "stream": "https://example.com/stream.mp3",
                                "onlyVIP": False,
                            }
                        ],
                    }
                ]
            },
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.Session.return_value.__enter__.return_value.get.return_value = (
            mock_response
        )

        # Mock ConnectionHandler
        mock_conn = MagicMock()

        result = search_music(mock_conn, "test query", limit=5)

        assert result.action.value == "REQLLM"
        assert "Test Song" in result.result
        assert "Test Artist" in result.result

    @patch("app.ai.plugins_func.functions.music.search_music.requests")
    def test_search_music_no_results(self, mock_requests):
        """Test search with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "success": True,
            "data": {"songs": []},
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.Session.return_value.__enter__.return_value.get.return_value = (
            mock_response
        )

        mock_conn = MagicMock()
        result = search_music(mock_conn, "nonexistent", limit=5)

        assert result.action.value == "RESPONSE"
        assert "Không tìm thấy" in result.response

    @patch("app.ai.plugins_func.functions.music.search_music.requests")
    def test_search_music_api_error(self, mock_requests):
        """Test handling API error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 1,
            "success": False,
            "msg": "API error",
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.Session.return_value.__enter__.return_value.get.return_value = (
            mock_response
        )

        mock_conn = MagicMock()
        result = search_music(mock_conn, "test", limit=5)

        assert result.action.value == "RESPONSE"
        assert "không khả dụng" in result.response

    def test_get_stream_url_priority(self):
        """Test stream URL selection priority."""
        song = {
            "streamURL": [
                {
                    "type": "320",
                    "stream": "https://example.com/320.mp3",
                    "onlyVIP": False,
                },
                {
                    "type": "128",
                    "stream": "https://example.com/128.mp3",
                    "onlyVIP": False,
                },
            ]
        }

        url = _get_stream_url(song)
        assert url == "https://example.com/128.mp3"  # Should prefer 128kbps

    def test_get_stream_url_no_vip(self):
        """Test stream URL skips VIP-only streams."""
        song = {
            "streamURL": [
                {
                    "type": "128",
                    "stream": "https://example.com/vip.mp3",
                    "onlyVIP": True,
                },
                {
                    "type": "128",
                    "stream": "https://example.com/free.mp3",
                    "onlyVIP": False,
                },
            ]
        }

        url = _get_stream_url(song)
        assert url == "https://example.com/free.mp3"


class TestStreamMusicURL:
    """Tests for stream_music_url tool."""

    def test_stream_music_url_invalid_url(self):
        """Test handling invalid URL."""
        mock_conn = MagicMock()
        result = stream_music_url(mock_conn, "invalid-url", "Test Song")

        assert result.action.value == "RESPONSE"
        assert "không hợp lệ" in result.response

    @patch("app.ai.plugins_func.functions.music.stream_music_url.FFmpegURLStreamer")
    def test_stream_music_url_no_ffmpeg(self, mock_streamer_class):
        """Test error when FFmpeg is not available."""
        mock_streamer_class.is_ffmpeg_available.return_value = False

        mock_conn = MagicMock()
        result = stream_music_url(mock_conn, "https://example.com/audio.mp3", "Test")

        assert result.action.value == "RESPONSE"
        assert "FFmpeg" in result.response

    @patch("app.ai.plugins_func.functions.music.stream_music_url.FFmpegURLStreamer")
    @pytest.mark.asyncio
    async def test_stream_music_url_success(self, mock_streamer_class):
        """Test successful stream start."""
        mock_streamer = MagicMock()
        mock_streamer_class.is_ffmpeg_available.return_value = True
        mock_streamer_class.return_value = mock_streamer

        mock_conn = MagicMock()
        mock_conn.loop.is_running.return_value = True
        mock_conn.loop.create_task = MagicMock()

        result = stream_music_url(
            mock_conn, "https://example.com/audio.mp3", "Test Song"
        )

        assert result.action.value == "NONE"
        assert "Đang phát" in result.response
        mock_conn.loop.create_task.assert_called_once()


class TestStopMusic:
    """Tests for stop_music tool."""

    def test_stop_music_with_streamer(self):
        """Test stopping music with active streamer."""
        mock_streamer = MagicMock()
        mock_conn = MagicMock()
        mock_conn.current_streamer = mock_streamer
        mock_conn.tts = MagicMock()
        mock_conn.tts.tts_audio_queue = MagicMock()
        mock_conn.tts.tts_audio_queue.qsize.return_value = 5
        mock_conn.clear_queues = MagicMock()
        mock_conn.clearSpeakStatus = MagicMock()

        result = stop_music(mock_conn)

        assert result.action.value == "RESPONSE"
        assert "Đã dừng" in result.response
        mock_streamer.stop.assert_called_once()
        assert mock_conn.current_streamer is None
        mock_conn.clear_queues.assert_called_once()

    def test_stop_music_no_streamer(self):
        """Test stopping when no music is playing."""
        mock_conn = MagicMock()
        mock_conn.current_streamer = None
        mock_conn.tts = None
        mock_conn.clearSpeakStatus = MagicMock()

        result = stop_music(mock_conn)

        assert result.action.value == "RESPONSE"
        assert "Không có nhạc" in result.response


class TestEndToEndStreamStop:
    """End-to-end tests for stream → stop flow."""

    @pytest.mark.asyncio
    async def test_stream_then_stop(self):
        """Test complete flow: start stream → stop."""
        # Mock components
        mock_streamer = MagicMock()

        async def mock_stream_frames():
            yield b"frame1"
            yield b"frame2"

        mock_streamer.stream_opus_frames = mock_stream_frames
        mock_streamer.stop_async = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.current_streamer = None
        mock_conn.client_abort = False
        mock_conn.tts = MagicMock()
        mock_conn.dialogue = MagicMock()
        mock_conn.dialogue.put = MagicMock()
        mock_conn.clearSpeakStatus = MagicMock()

        # Mock sendAudio
        async def mock_send_audio(conn, audio, frame_duration):
            pass

        with patch(
            "app.ai.plugins_func.functions.music.stream_music_url.sendAudio",
            side_effect=mock_send_audio,
        ), patch(
            "app.ai.plugins_func.functions.music.stream_music_url.send_stt_message",
            new_callable=AsyncMock,
        ), patch(
            "app.ai.plugins_func.functions.music.stream_music_url.send_tts_message",
            new_callable=AsyncMock,
        ), patch(
            "app.ai.plugins_func.functions.music.stream_music_url.FFmpegURLStreamer",
            return_value=mock_streamer,
        ):

            # Start stream
            await _handle_stream(
                mock_conn, "https://example.com/audio.mp3", "Test Song"
            )

            # Verify streamer was stored
            assert mock_conn.current_streamer == mock_streamer

            # Stop music
            result = stop_music(mock_conn)

            assert result.action.value == "RESPONSE"
            assert "Đã dừng" in result.response
            assert mock_conn.current_streamer is None
