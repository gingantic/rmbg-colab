"""Shared fixtures for API and service tests."""

import io

import pikepdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def app():
    """Fresh ASGI app (avoids shared state across tests)."""
    from app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def tiny_rgba_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), color=(0, 255, 0, 128)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def minimal_pdf_bytes() -> bytes:
    """Single blank-page PDF built with pikepdf."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(72, 72))
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()
