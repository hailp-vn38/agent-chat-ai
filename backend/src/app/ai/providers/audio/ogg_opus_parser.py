"""
Ogg container parser để extract Opus frames.

Ogg page format:
- 4 bytes: "OggS" magic
- 1 byte: version (0)
- 1 byte: header type flags
- 8 bytes: granule position (little-endian)
- 4 bytes: serial number
- 4 bytes: page sequence number
- 4 bytes: CRC checksum
- 1 byte: number of segments
- N bytes: segment table (N = number of segments)
- Payload data (segmented into packets based on segment table)

Segment table rules:
- Each segment size is 0-255 bytes
- Segments with size < 255 mark end of a packet
- Segments with size = 255 continue the packet in next segment
"""

from __future__ import annotations

from app.core.logger import setup_logging

TAG = __name__
logger = setup_logging()

OGG_MAGIC = b"OggS"
OGG_HEADER_SIZE = 27  # Fixed header size before segment table


class OggOpusParser:
    """Parse Ogg container để extract individual Opus packets."""

    def __init__(self):
        self.buffer = bytearray()
        self._header_packets_skipped = 0
        self._total_packets = 0

    def feed(self, data: bytes) -> list[bytes]:
        """
        Feed data và return list of individual opus packets.

        Args:
            data: Raw bytes từ FFmpeg stdout

        Returns:
            List of Opus packet bytes (có thể rỗng nếu chưa đủ data)
        """
        self.buffer.extend(data)
        packets = []

        while len(self.buffer) >= OGG_HEADER_SIZE:
            # Check OggS magic
            if self.buffer[:4] != OGG_MAGIC:
                # Tìm OggS marker tiếp theo để resync
                idx = self.buffer.find(OGG_MAGIC, 1)
                if idx == -1:
                    # Không tìm thấy, giữ lại 3 bytes cuối (có thể là partial magic)
                    self.buffer = (
                        self.buffer[-3:] if len(self.buffer) > 3 else bytearray()
                    )
                    break
                logger.bind(tag=TAG).debug(
                    f"[OggOpusParser] Resync: skipped {idx} bytes"
                )
                self.buffer = self.buffer[idx:]
                continue

            # Parse header
            num_segments = self.buffer[26]
            header_total = OGG_HEADER_SIZE + num_segments

            if len(self.buffer) < header_total:
                break  # Chưa đủ segment table

            # Read segment table
            segment_table = list(self.buffer[OGG_HEADER_SIZE:header_total])
            payload_size = sum(segment_table)
            page_size = header_total + payload_size

            if len(self.buffer) < page_size:
                break  # Chưa đủ payload

            # Extract granule position để skip header pages
            granule = int.from_bytes(self.buffer[6:14], "little")

            # Extract payload
            payload = self.buffer[header_total:page_size]

            # Skip Opus header pages (OpusHead và OpusTags)
            # Header pages có granule_position = 0
            if granule == 0:
                self._header_packets_skipped += 1
            else:
                # Parse payload into individual packets using segment table
                page_packets = self._parse_packets(payload, segment_table)
                packets.extend(page_packets)

            # Remove processed page from buffer
            self.buffer = self.buffer[page_size:]

        return packets

    def _parse_packets(
        self, payload: bytearray, segment_table: list[int]
    ) -> list[bytes]:
        """
        Parse payload into individual packets based on segment table.

        Segment rules:
        - Segment size < 255: packet ends
        - Segment size = 255: packet continues in next segment
        """
        packets = []
        current_packet = bytearray()
        offset = 0

        for segment_size in segment_table:
            # Add segment to current packet
            current_packet.extend(payload[offset : offset + segment_size])
            offset += segment_size

            # If segment_size < 255, packet is complete
            if segment_size < 255:
                if current_packet:
                    packets.append(bytes(current_packet))
                    self._total_packets += 1
                current_packet = bytearray()

        # Handle case where last segment was 255 (incomplete packet)
        # This packet will be completed in next page
        if current_packet:
            # For streaming, we still yield it (may cause slight audio glitch)
            packets.append(bytes(current_packet))
            self._total_packets += 1

        return packets

    def reset(self):
        """Reset parser state."""
        self.buffer.clear()
        self._header_packets_skipped = 0
        self._total_packets = 0

    @property
    def total_packets(self) -> int:
        """Total number of packets parsed."""
        return self._total_packets
