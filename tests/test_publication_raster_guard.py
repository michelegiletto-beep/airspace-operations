"""Isolated container fixtures only; no operational images or publication writes."""
import base64
from pathlib import Path
import struct
import sys
import zlib

from hypothesis import given, settings, strategies as st
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publication_media as media

# These tiny fixtures were generated for software tests with Pillow13.0.0.
# The guard itself has no Pillow dependency and does not decode pixels.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUMvZlYGBgYgADAAcvAJ6LDLezAAAAAElFTkSuQmCC")
JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AMn//2Q==")
WEBP = base64.b64decode("UklGRjIAAABXRUJQVlA4ICYAAACQAQCdASoCAAIAAUAmJQBOl0AAjNAA/vl9v8WxSG5nxC72MKAAAA==")
LOSSLESS_WEBP = base64.b64decode("UklGRh4AAABXRUJQVlA4TBEAAAAvAUAAEAfQmWq0qYCBiOh/AAA=")
PROGRESSIVE_JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wgARCAACAAIDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUAQEAAAAAAAAAAAAAAAAAAAAD/9oADAMBAAIQAxAAAAGWDh//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAn//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AX//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AX//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/An//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IX//2gAMAwEAAgADAAAAEA//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EH//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EH//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EH//2Q==")


@pytest.mark.parametrize("suffix,data,expected", [
    (".png", PNG, "PNG"), (".PNG", PNG, "PNG"), (".jpg", JPEG, "JPEG"),
    (".jpeg", JPEG, "JPEG"), (".JPEG", PROGRESSIVE_JPEG, "JPEG"),
    (".webp", WEBP, "WEBP"), (".webp", LOSSLESS_WEBP, "WEBP"),
])
def test_actual_framed_encoding_matches_filename_without_rewriting(tmp_path, suffix, data, expected):
    path = tmp_path / ("isolated" + suffix)
    path.write_bytes(data)
    assert media.validate_raster_encoding(path) == expected
    assert path.read_bytes() == data


@pytest.mark.parametrize("suffix,data", [(".png", JPEG), (".jpg", PNG), (".webp", PNG), (".png", WEBP), (".jpeg", WEBP), (".webp", JPEG)])
def test_misnamed_raster_is_rejected(tmp_path, suffix, data):
    path = tmp_path / ("isolated" + suffix)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="filename requires"):
        media.validate_raster_encoding(path)


@pytest.mark.parametrize("suffix,data", [(".png", PNG), (".jpg", JPEG), (".webp", WEBP)])
def test_signature_alone_and_trailing_payload_are_not_accepted(tmp_path, suffix, data):
    path = tmp_path / ("isolated" + suffix)
    for content in (data[:12], data[:-1], data + b"unexpected trailing payload"):
        path.write_bytes(content)
        with pytest.raises(ValueError):
            media.validate_raster_encoding(path)


def png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def test_png_crc_header_and_required_data_are_checked(tmp_path):
    path = tmp_path / "isolated.png"
    bad_crc = bytearray(PNG)
    bad_crc[45] ^= 1
    zero_width = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 0, 2, 8, 2, 0, 0, 0))
    excessive_width = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 2**31, 2, 8, 2, 0, 0, 0))
    for content in (bad_crc, PNG[:8] + zero_width + PNG[33:], PNG[:8] + excessive_width + PNG[33:], PNG[:33] + PNG[-12:], PNG[:33] + PNG[8:33] + PNG[33:]):
        path.write_bytes(content)
        with pytest.raises(ValueError):
            media.validate_raster_encoding(path)


def test_jpeg_requires_complete_frame_scan_and_end_segments(tmp_path):
    path = tmp_path / "isolated.jpg"
    for content in (b"\xff\xd8\xff\xd9", JPEG[:20] + b"\xff\xd9", b"\xff\xd8\xff\xe0\xff\xffpayload\xff\xd9"):
        path.write_bytes(content)
        with pytest.raises(ValueError):
            media.validate_raster_encoding(path)


def test_webp_requires_riff_length_and_complete_frame_header(tmp_path):
    path = tmp_path / "isolated.webp"
    wrong_length = bytearray(WEBP)
    wrong_length[4:8] = (len(WEBP) + 5).to_bytes(4, "little")
    bad_frame = bytearray(WEBP)
    bad_frame[23] ^= 1
    for content in (wrong_length, bad_frame, b"RIFF\x04\x00\x00\x00WEBP"):
        path.write_bytes(content)
        with pytest.raises(ValueError):
            media.validate_raster_encoding(path)


def test_size_empty_and_unsupported_encoding_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "isolated.png"
    for content in (b"", b"<svg>software fixture only</svg>", b"GIF89a"):
        path.write_bytes(content)
        with pytest.raises(ValueError):
            media.validate_raster_encoding(path)
    path.write_bytes(PNG)
    monkeypatch.setattr(media, "MAX_RASTER_BYTES", len(PNG) - 1)
    with pytest.raises(ValueError, match="bounded size"):
        media.validate_raster_encoding(path)


def test_webp_extended_still_header_and_animation_declaration_are_distinct(tmp_path):
    path = tmp_path / "isolated.webp"
    for flags in (0, 2):
        header = bytes([flags, 0, 0, 0, 1, 0, 0, 1, 0, 0])
        chunks = b"VP8X" + struct.pack("<I", len(header)) + header + WEBP[12:]
        path.write_bytes(b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + chunks)
        if flags:
            with pytest.raises(ValueError, match="single frame"):
                media.validate_raster_encoding(path)
        else:
            assert media.validate_raster_encoding(path) == "WEBP"


@settings(max_examples=80, deadline=None)
@given(st.binary(max_size=512))
def test_malformed_containers_raise_validation_errors_not_parser_failures(payload):
    for prefix, parser in ((b"\x89PNG\r\n\x1a\n", media._png), (b"\xff\xd8", media._jpeg), (b"RIFF\x00\x00\x00\x00WEBP", media._webp)):
        try:
            parser(prefix + payload)
        except ValueError:
            pass
