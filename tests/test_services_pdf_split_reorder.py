"""Tests for app.services.pdf_split_reorder."""

import io
import zipfile

import pikepdf
import pytest
from pypdf import PdfReader

from app.services.pdf_split_reorder import (
    build_reordered_pdf,
    build_split_zip,
    parse_block_order_json,
    parse_page_order_json,
    parse_split_ranges,
)


def _multi_page_pdf_bytes(page_count: int) -> bytes:
    pdf = pikepdf.Pdf.new()
    for _ in range(page_count):
        pdf.add_blank_page(page_size=(72, 72))
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def test_parse_split_ranges_ok():
    blocks = parse_split_ranges("1-2|3,4", 4)
    assert blocks == [[0, 1], [2, 3]]


def test_parse_split_ranges_invalid():
    with pytest.raises(ValueError):
        parse_split_ranges("1-a|2", 3)


def test_parse_page_order_json_default_and_custom():
    assert parse_page_order_json("", 3) == [0, 1, 2]
    assert parse_page_order_json("[3,1,2]", 3) == [2, 0, 1]


def test_parse_block_order_json_default_and_custom():
    assert parse_block_order_json("", 2) == [0, 1]
    assert parse_block_order_json("[2,1]", 2) == [1, 0]


def test_build_reordered_pdf():
    raw = _multi_page_pdf_bytes(3)
    out = build_reordered_pdf(raw, [2, 0, 1])
    parsed = PdfReader(io.BytesIO(out))
    assert len(parsed.pages) == 3


def test_build_split_zip():
    raw = _multi_page_pdf_bytes(4)
    out = build_split_zip(raw, [[0, 1], [2, 3]], [1, 0])
    z = zipfile.ZipFile(io.BytesIO(out))
    names = z.namelist()
    assert names == ["part_01.pdf", "part_02.pdf"]
