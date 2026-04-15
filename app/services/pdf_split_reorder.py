"""Split and reorder a PDF into a single PDF or ZIP of split parts."""

from __future__ import annotations

import io
import json
import zipfile

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from app.config import get_settings


def parse_split_ranges(raw: str, page_count: int) -> list[list[int]]:
    """Parse split ranges like ``1-3,5|6-8`` into 0-based block page indices.

    Blocks are separated by ``|``.
    Page tokens inside a block are separated by commas.
    """
    if page_count < 1:
        raise ValueError("PDF has no pages.")
    text = (raw or "").strip()
    if not text:
        return []

    blocks: list[list[int]] = []
    for block_raw in text.split("|"):
        block_text = block_raw.strip()
        if not block_text:
            continue
        page_nums: list[int] = []
        for token_raw in block_text.split(","):
            token = token_raw.strip()
            if not token:
                continue
            if "-" in token:
                start_s, end_s = token.split("-", 1)
                if not start_s.strip().isdigit() or not end_s.strip().isdigit():
                    raise ValueError(f"Invalid range token: {token}")
                start = int(start_s.strip())
                end = int(end_s.strip())
                if start > end:
                    raise ValueError(f"Invalid range token: {token}")
                page_nums.extend(range(start, end + 1))
            else:
                if not token.isdigit():
                    raise ValueError(f"Invalid page token: {token}")
                page_nums.append(int(token))

        if not page_nums:
            raise ValueError("Split block cannot be empty.")
        if any(p < 1 or p > page_count for p in page_nums):
            raise ValueError(f"Split range must be within 1..{page_count}.")
        if len(set(page_nums)) != len(page_nums):
            raise ValueError("Split ranges cannot include duplicate pages.")
        blocks.append([p - 1 for p in page_nums])

    if not blocks:
        return []
    return blocks


def parse_page_order_json(raw: str, page_count: int) -> list[int]:
    """Parse a JSON array with 1-based page numbers into 0-based order."""
    text = (raw or "").strip()
    if not text:
        return list(range(page_count))
    try:
        arr = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid page order payload.") from e
    if not isinstance(arr, list) or not arr:
        raise ValueError("Page order must be a non-empty array.")
    if not all(isinstance(v, int) for v in arr):
        raise ValueError("Page order must contain integers only.")
    if any(v < 1 or v > page_count for v in arr):
        raise ValueError(f"Page order must be within 1..{page_count}.")
    if len(set(arr)) != page_count or len(arr) != page_count:
        raise ValueError("Page order must include every page exactly once.")
    return [v - 1 for v in arr]


def parse_block_order_json(raw: str, block_count: int) -> list[int]:
    """Parse a JSON array with 1-based split block indices into 0-based order."""
    if block_count < 1:
        return []
    text = (raw or "").strip()
    if not text:
        return list(range(block_count))
    try:
        arr = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid block order payload.") from e
    if not isinstance(arr, list) or not arr:
        raise ValueError("Block order must be a non-empty array.")
    if not all(isinstance(v, int) for v in arr):
        raise ValueError("Block order must contain integers only.")
    if any(v < 1 or v > block_count for v in arr):
        raise ValueError(f"Block order must be within 1..{block_count}.")
    if len(set(arr)) != block_count or len(arr) != block_count:
        raise ValueError("Block order must include every split block exactly once.")
    return [v - 1 for v in arr]


def parse_split_blocks_json(raw: str, page_count: int) -> list[list[int]]:
    """Parse JSON split blocks with 1-based page numbers into 0-based blocks."""
    text = (raw or "").strip()
    if not text:
        return []
    try:
        arr = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid split blocks payload.") from e
    if not isinstance(arr, list) or not arr:
        raise ValueError("Split blocks must be a non-empty array.")

    out: list[list[int]] = []
    for block in arr:
        if not isinstance(block, list) or not block:
            raise ValueError("Each split block must be a non-empty array.")
        if not all(isinstance(v, int) for v in block):
            raise ValueError("Split blocks must contain integers only.")
        if any(v < 1 or v > page_count for v in block):
            raise ValueError(f"Split blocks must be within 1..{page_count}.")
        if len(set(block)) != len(block):
            raise ValueError("Split blocks cannot include duplicate pages.")
        out.append([v - 1 for v in block])
    return out


def _read_pdf(raw_pdf: bytes) -> PdfReader:
    if not raw_pdf:
        raise ValueError("Empty file.")
    try:
        reader = PdfReader(io.BytesIO(raw_pdf))
    except PdfReadError as e:
        raise ValueError("Invalid PDF file.") from e
    except Exception as e:
        raise ValueError("Unable to read PDF file.") from e
    if len(reader.pages) == 0:
        raise ValueError("PDF has no pages.")
    max_pages = get_settings().max_pdf_pages
    if len(reader.pages) > max_pages:
        raise ValueError(f"Too many pages (maximum {max_pages}).")
    return reader


def get_pdf_page_count(raw_pdf: bytes) -> int:
    """Return validated page count for uploaded PDF."""
    return len(_read_pdf(raw_pdf).pages)


def parse_single_range(raw: str, page_count: int) -> tuple[int, int]:
    """Parse a single page or N-M range into 1-based (start, end).

    Accepts inputs like "5" or "3-7" and validates that:
    - both bounds are integers
    - 1 <= start <= end <= page_count
    """
    if page_count < 1:
        raise ValueError("PDF has no pages.")

    text = (raw or "").strip()
    if not text:
        raise ValueError("Page range is required.")

    if "-" in text:
        start_s, end_s = text.split("-", 1)
        start_s = start_s.strip()
        end_s = end_s.strip()
        if not start_s.isdigit() or not end_s.isdigit():
            raise ValueError("Enter a page like 5 or a range like 3-7.")
        start = int(start_s)
        end = int(end_s)
    else:
        if not text.isdigit():
            raise ValueError("Enter a page like 5 or a range like 3-7.")
        start = end = int(text)

    if start < 1 or end < 1 or start > page_count or end > page_count:
        raise ValueError(f"Page range must be within 1..{page_count}.")
    if start > end:
        raise ValueError("Start page cannot be greater than end page.")

    return start, end


def build_range_pdf(raw_pdf: bytes, start_page: int, end_page: int) -> bytes:
    """Build a PDF containing only pages in the inclusive 1-based range."""
    reader = _read_pdf(raw_pdf)
    if start_page < 1 or end_page < 1:
        raise ValueError("Page numbers must be positive.")
    if start_page > end_page:
        raise ValueError("Start page cannot be greater than end page.")
    if end_page > len(reader.pages):
        raise ValueError(f"Page range must be within 1..{len(reader.pages)}.")

    writer = PdfWriter()
    for num in range(start_page, end_page + 1):
        writer.add_page(reader.pages[num - 1])
    out = io.BytesIO()
    writer.write(out)
    writer.close()
    return out.getvalue()


def build_reordered_pdf(raw_pdf: bytes, page_order: list[int]) -> bytes:
    """Build a single PDF using a specific page order (0-based indices)."""
    reader = _read_pdf(raw_pdf)
    if len(page_order) != len(reader.pages):
        raise ValueError("Page order size must match PDF page count.")
    writer = PdfWriter()
    for idx in page_order:
        writer.add_page(reader.pages[idx])
    out = io.BytesIO()
    writer.write(out)
    writer.close()
    return out.getvalue()


def build_split_zip(raw_pdf: bytes, split_blocks: list[list[int]], block_order: list[int]) -> bytes:
    """Build ZIP containing split PDFs in the selected block order."""
    if not split_blocks:
        raise ValueError("No split ranges provided.")
    if len(block_order) != len(split_blocks):
        raise ValueError("Block order size must match split block count.")

    reader = _read_pdf(raw_pdf)
    all_pages = set(range(len(reader.pages)))
    used_pages = {p for block in split_blocks for p in block}
    if used_pages != all_pages:
        raise ValueError("Split ranges must cover all pages exactly once.")
    if sum(len(block) for block in split_blocks) != len(all_pages):
        raise ValueError("Split ranges cannot include duplicate pages.")

    out_zip = io.BytesIO()
    with zipfile.ZipFile(out_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for out_idx, block_idx in enumerate(block_order, start=1):
            block_pages = split_blocks[block_idx]
            writer = PdfWriter()
            for page_idx in block_pages:
                writer.add_page(reader.pages[page_idx])
            part_buf = io.BytesIO()
            writer.write(part_buf)
            writer.close()
            zf.writestr(f"part_{out_idx:02d}.pdf", part_buf.getvalue())
    return out_zip.getvalue()
