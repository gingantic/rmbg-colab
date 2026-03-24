"""Merge ordered PDF byte streams into one PDF."""

import io

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.config import get_settings


def merge_pdf_bytes(parts: list[bytes]) -> bytes:
    """Return a single merged PDF preserving input order."""
    if not parts:
        raise ValueError("No PDF files provided.")

    max_pages = get_settings().max_pdf_pages
    writer = PdfWriter()
    total_pages = 0

    for raw in parts:
        if not raw:
            raise ValueError("Empty file.")
        try:
            reader = PdfReader(io.BytesIO(raw))
        except PdfReadError as e:
            raise ValueError("Invalid PDF file.") from e
        except Exception as e:
            raise ValueError("Unable to read one of the PDF files.") from e

        if len(reader.pages) == 0:
            raise ValueError("One of the PDF files has no pages.")

        total_pages += len(reader.pages)
        if total_pages > max_pages:
            raise ValueError(f"Too many pages (maximum {max_pages}).")

        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    writer.close()
    return out.getvalue()
