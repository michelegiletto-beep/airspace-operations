"""Bounded raster container checks for publication; this is not pixel decoding."""
from __future__ import annotations

from pathlib import Path
import struct
import zlib


RASTER_SUFFIXES = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
MAX_RASTER_BYTES = 32 * 1024 * 1024


def _png(data: bytes) -> None:
    offset, chunks, saw_data = 8, 0, False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset:offset + 4], "big")
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data) or not all(65 <= value <= 90 or 97 <= value <= 122 for value in kind):
            raise ValueError("Invalid PNG chunk framing")
        payload = data[offset + 8:end - 4]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != int.from_bytes(data[end - 4:end], "big"):
            raise ValueError("Invalid PNG chunk checksum")
        if chunks == 0:
            if kind != b"IHDR" or length != 13:
                raise ValueError("PNG must begin with its image header")
            width, height, depth, colour, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if (not 0 < width < 2**31 or not 0 < height < 2**31 or depth not in depths.get(colour, set())
                    or compression or filtering or interlace not in {0, 1}):
                raise ValueError("Invalid PNG image header")
        elif kind == b"IHDR":
            raise ValueError("Duplicate PNG image header")
        if kind == b"IDAT" and length:
            saw_data = True
        if kind == b"IEND":
            if length or not saw_data or end != len(data):
                raise ValueError("Invalid PNG image end or missing image data")
            return
        offset, chunks = end, chunks + 1
    raise ValueError("Truncated PNG container")


def _jpeg(data: bytes) -> None:
    offset, saw_frame, saw_scan = 2, False, False
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        if data[offset] != 0xFF:
            raise ValueError("Invalid JPEG marker framing")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset == len(data):
            break
        marker, offset = data[offset], offset + 1
        if marker == 0xD9:
            if offset != len(data) or not saw_frame or not saw_scan:
                raise ValueError("Invalid JPEG image end or missing frame/scan")
            return
        if marker == 0x01:
            continue
        if marker in {0x00, 0xD8} or 0xD0 <= marker <= 0xD7 or offset + 2 > len(data):
            raise ValueError("Invalid JPEG segment marker")
        length = int.from_bytes(data[offset:offset + 2], "big")
        end = offset + length
        if length < 2 or end > len(data):
            raise ValueError("Truncated JPEG segment")
        payload = data[offset + 2:end]
        if marker in frame_markers:
            if (len(payload) < 6 or not int.from_bytes(payload[1:3], "big")
                    or not int.from_bytes(payload[3:5], "big") or not payload[5]
                    or len(payload) != 6 + 3 * payload[5]):
                raise ValueError("Invalid JPEG frame header")
            saw_frame = True
        offset = end
        if marker == 0xDA:
            if not saw_frame or not payload or not payload[0] or len(payload) != 4 + 2 * payload[0]:
                raise ValueError("Invalid JPEG scan header")
            saw_scan = True
            # Entropy data escapes FF as FF00 and permits restart markers. A
            # different marker returns control to the outer segment parser.
            while offset < len(data):
                if data[offset] != 0xFF:
                    offset += 1
                    continue
                start = offset
                while offset < len(data) and data[offset] == 0xFF:
                    offset += 1
                if offset == len(data):
                    break
                following = data[offset]
                if following in {0x00, 0x01} or 0xD0 <= following <= 0xD7:
                    offset += 1
                    continue
                offset = start
                break
    raise ValueError("Truncated JPEG container")


def _webp(data: bytes) -> None:
    if len(data) < 20 or int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError("Invalid WebP RIFF length")
    offset, saw_frame, saw_extended = 12, False, False
    while offset + 8 <= len(data):
        kind = data[offset:offset + 4]
        length = int.from_bytes(data[offset + 4:offset + 8], "little")
        end = offset + 8 + length
        padded = end + length % 2
        if padded > len(data) or (length % 2 and data[end] != 0):
            raise ValueError("Invalid WebP chunk framing")
        payload = data[offset + 8:end]
        if kind == b"VP8X":
            if saw_extended or offset != 12 or length != 10 or payload[0] & 0xC1 or any(payload[1:4]):
                raise ValueError("Invalid WebP extended header")
            if payload[0] & 0x02:
                raise ValueError("Publication WebP screenshots must contain a single frame")
            saw_extended = True
        elif kind == b"VP8 ":
            if (saw_frame or length < 10 or payload[0] & 1 or payload[3:6] != b"\x9d\x01\x2a"
                    or not int.from_bytes(payload[6:8], "little") & 0x3FFF
                    or not int.from_bytes(payload[8:10], "little") & 0x3FFF):
                raise ValueError("Invalid WebP VP8 frame header")
            saw_frame = True
        elif kind == b"VP8L":
            if saw_frame or length < 5 or payload[0] != 0x2F or payload[4] & 0xE0:
                raise ValueError("Invalid WebP lossless frame header")
            saw_frame = True
        elif kind in {b"ANIM", b"ANMF"}:
            raise ValueError("Publication WebP screenshots must contain a single frame")
        offset = padded
    if offset != len(data) or not saw_frame:
        raise ValueError("Truncated WebP container or missing image frame")


def validate_raster_encoding(path: Path) -> str:
    """Match extension to framed PNG/JPEG/single-frame WebP bytes, read only.

    Container structure, PNG CRCs and required image headers are checked. Image
    data is not decompressed or decoded; browser display and visual review remain
    separate release evidence. No existing image is renamed or rewritten.
    """
    expected = RASTER_SUFFIXES.get(path.suffix.lower())
    if expected is None:
        raise ValueError("Publication image extension is unsupported")
    with path.open("rb") as source:
        data = source.read(MAX_RASTER_BYTES + 1)
    if not data or len(data) > MAX_RASTER_BYTES:
        raise ValueError("Publication raster exceeds the bounded size or is empty")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        actual, check = "PNG", _png
    elif data.startswith(b"\xff\xd8"):
        actual, check = "JPEG", _jpeg
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        actual, check = "WEBP", _webp
    else:
        raise ValueError("Publication raster encoding is unsupported")
    if actual != expected:
        raise ValueError(f"Publication raster filename requires {expected}, but its bytes identify {actual}: {path.name}")
    check(data)
    return actual
