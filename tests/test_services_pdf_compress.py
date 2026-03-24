"""Tests for app.services.pdf_compress."""

import pytest

from app.services.pdf_compress import compress_pdf_bytes


def test_compress_pdf_bytes_minimal(minimal_pdf_bytes):
    out, mode, kept = compress_pdf_bytes(minimal_pdf_bytes, 85, "auto")
    assert isinstance(out, bytes)
    assert len(out) > 0
    assert mode in ("text", "image")
    assert isinstance(kept, bool)


def test_compress_pdf_bytes_invalid_raises():
    with pytest.raises(ValueError):
        compress_pdf_bytes(b"not a pdf", 85, "auto")


def test_compress_pdf_bytes_bitmap_mode(minimal_pdf_bytes):
    out, mode, kept = compress_pdf_bytes(minimal_pdf_bytes, 75, "bitmap", bitmap_dpi=120)
    assert mode == "bitmap"
    assert isinstance(out, bytes)
    assert len(out) > 0
    assert out.startswith(b"%PDF")
    assert isinstance(kept, bool)
