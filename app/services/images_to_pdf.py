"""Merge raster images into one PDF via img2pdf."""

import io

import img2pdf
from PIL import Image

from app.config import get_settings
from app.utils.image_safe import open_uploaded_image


def _image_to_img2pdf_stream(im: Image.Image) -> io.BytesIO:
    """Encode PIL image to PNG or JPEG in memory for img2pdf."""
    buf = io.BytesIO()
    im.load()
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode in ("RGBA", "LA"):
        if im.mode == "LA":
            im = im.convert("RGBA")
        im.save(buf, format="PNG", optimize=True)
    elif im.mode == "CMYK":
        im.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
    else:
        im.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
    buf.seek(0)
    return buf


def images_bytes_to_pdf(parts: list[bytes]) -> bytes:
    """
    Build a single PDF from ordered image bytes. Each item is decoded with
    Pillow limits; page order follows ``parts``.
    """
    if not parts:
        raise ValueError("No images provided.")

    max_pages = get_settings().max_pdf_pages
    if len(parts) > max_pages:
        raise ValueError(f"Too many images (maximum {max_pages}).")

    streams: list[io.BytesIO] = []
    try:
        for raw in parts:
            if not raw:
                raise ValueError("Empty image file.")
            im = open_uploaded_image(raw)
            streams.append(_image_to_img2pdf_stream(im))
        return img2pdf.convert(streams)
    finally:
        for s in streams:
            try:
                s.close()
            except Exception:
                pass
