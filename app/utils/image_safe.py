"""Decode uploaded image bytes with strict pixel / edge limits."""

import io

from PIL import Image

from app.config import get_settings


def ensure_image_within_limits(im: Image.Image) -> None:
    """Raise ValueError if width/height/pixel count exceed configured limits."""
    w, h = im.size
    s = get_settings()
    if w * h > s.max_image_pixels:
        raise ValueError("Image has too many pixels.")
    if w > s.max_image_edge_px or h > s.max_image_edge_px:
        raise ValueError("Image width or height exceeds the maximum allowed.")


def open_uploaded_image(raw: bytes) -> Image.Image:
    """
    Open image from bytes, force decode (triggers Pillow decompression limits),
    then enforce max pixels and max edge length from settings.
    """
    im = Image.open(io.BytesIO(raw))
    im.load()
    ensure_image_within_limits(im)
    return im
