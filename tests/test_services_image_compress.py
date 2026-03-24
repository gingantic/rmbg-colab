"""Tests for app.services.image_compress."""

import io

import pytest
from PIL import Image

from app.services.image_compress import (
    CONVERT_FORMATS,
    OUTPUT_FORMATS,
    compress_to_buffer,
    convert_to_buffer,
)


def test_compress_jpeg_rgb():
    im = Image.new("RGB", (8, 8), color=(10, 20, 30))
    buf, mimetype, ext = compress_to_buffer(im, "jpeg", 80)
    assert mimetype == "image/jpeg"
    assert ext == "jpg"
    assert len(buf.getvalue()) > 0


def test_compress_png_rgba():
    im = Image.new("RGBA", (4, 4), color=(255, 0, 0, 200))
    buf, mimetype, ext = compress_to_buffer(im, "png", 50)
    assert mimetype == "image/png"
    assert ext == "png"
    assert len(buf.getvalue()) > 0


def test_compress_webp():
    im = Image.new("RGB", (8, 8), color=(0, 0, 0))
    buf, mimetype, ext = compress_to_buffer(im, "webp", 90)
    assert mimetype == "image/webp"
    assert ext == "webp"
    assert len(buf.getvalue()) > 0


def test_unsupported_format_raises():
    im = Image.new("RGB", (2, 2))
    with pytest.raises(ValueError, match="Unsupported"):
        compress_to_buffer(im, "gif", 85)


def test_output_formats_frozen():
    assert OUTPUT_FORMATS == {"jpeg", "webp", "png"}


@pytest.mark.parametrize(
    "fmt,mime,ext",
    [
        ("gif", "image/gif", "gif"),
        ("bmp", "image/bmp", "bmp"),
        ("tiff", "image/tiff", "tiff"),
    ],
)
def test_convert_additional_formats(fmt, mime, ext):
    im = Image.new("RGB", (8, 8), color=(123, 45, 67))
    buf, mimetype, out_ext = convert_to_buffer(im, fmt, 85)
    assert mimetype == mime
    assert out_ext == ext
    assert len(buf.getvalue()) > 0


def test_convert_invalid_format_raises():
    im = Image.new("RGB", (2, 2))
    with pytest.raises(ValueError, match="Invalid format"):
        convert_to_buffer(im, "avif", 85)


def test_convert_formats_frozen():
    assert CONVERT_FORMATS == {"jpeg", "webp", "png", "gif", "bmp", "tiff"}


def test_convert_resize_percent():
    im = Image.new("RGB", (100, 100), color=(1, 2, 3))
    buf, _, _ = convert_to_buffer(im, "png", 85, scale_percent=50)
    out = Image.open(io.BytesIO(buf.getvalue()))
    assert out.size == (50, 50)


def test_convert_full_resolution_unchanged_size():
    im = Image.new("RGB", (10, 10), color=(1, 2, 3))
    buf, _, _ = convert_to_buffer(im, "png", 85, scale_percent=100)
    out = Image.open(io.BytesIO(buf.getvalue()))
    assert out.size == (10, 10)
