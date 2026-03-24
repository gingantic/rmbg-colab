"""Tests for app.utils.files."""

import pytest

from app.utils.files import allowed_file, allowed_pdf_file


@pytest.mark.parametrize(
    "name,expected",
    [
        ("a.png", True),
        ("x.JPG", True),
        ("file.jpeg", True),
        ("p.webp", True),
        ("noext", False),
        (".hidden", False),
        ("bad.exe", False),
        ("", False),
    ],
)
def test_allowed_file(name, expected):
    assert allowed_file(name) is expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("doc.pdf", True),
        ("X.PDF", True),
        ("nope", False),
        ("bad.pdf.txt", False),
    ],
)
def test_allowed_pdf_file(name, expected):
    assert allowed_pdf_file(name) is expected
