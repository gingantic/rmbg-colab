"""PDF page rasterization to a ZIP of images (PDFium + Pillow)."""

import io
import zipfile

import pypdfium2 as pdfium

from app.config import get_settings
from app.services.image_compress import compress_to_buffer
from app.utils.image_safe import ensure_image_within_limits
from app.utils.quality import normalize_quality

PDF_TO_IMAGE_FORMATS = frozenset({"jpeg", "png", "webp"})


def pdf_bytes_to_images_zip(data: bytes, fmt: str, dpi: int, quality: int) -> bytes:
    """
    Render each PDF page to an image and return a ZIP of page_NNN.ext files.

    ``fmt`` must be jpeg, png, or webp. ``dpi`` is clamped 72–300. ``quality``
    applies to lossy formats (jpeg, webp).
    """
    fmt = (fmt or "png").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in PDF_TO_IMAGE_FORMATS:
        allowed = ", ".join(sorted(PDF_TO_IMAGE_FORMATS))
        raise ValueError(f"Invalid format. Use one of: {allowed}.")

    quality = normalize_quality(quality)
    dpi = max(72, min(300, int(dpi)))

    try:
        doc = pdfium.PdfDocument(io.BytesIO(data))
    except Exception as e:
        raise ValueError(
            "Could not open this PDF for rasterization (it may be encrypted or corrupted)."
        ) from e

    n = len(doc)
    max_pages = get_settings().max_pdf_pages
    if n > max_pages:
        raise ValueError(f"This PDF has too many pages (maximum {max_pages}).")
    if n < 1:
        raise ValueError("PDF has no pages.")

    scale = dpi / 72.0
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(n):
            page = doc[i]
            pil = page.render(scale=scale).to_pil()
            ensure_image_within_limits(pil)
            buf, _m, ext = compress_to_buffer(pil, fmt, quality)
            name = f"page_{i + 1:03d}.{ext}"
            zf.writestr(name, buf.getvalue())

    return zip_buf.getvalue()
