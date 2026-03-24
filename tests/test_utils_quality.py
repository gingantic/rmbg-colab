"""Tests for app.utils.quality."""

import pytest

from app.utils.quality import normalize_quality, normalize_scale_percent


@pytest.mark.parametrize(
    "raw,expected",
    [
        (50, 50),
        (1, 1),
        (100, 100),
        (0, 1),
        (200, 100),
        ("75", 75),
        ("bad", 85),
        (None, 85),
    ],
)
def test_normalize_quality(raw, expected):
    assert normalize_quality(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (100, 100),
        (50, 50),
        (1, 1),
        (0, 1),
        (150, 100),
        ("75", 75),
        ("bad", 100),
        (None, 100),
    ],
)
def test_normalize_scale_percent(raw, expected):
    assert normalize_scale_percent(raw) == expected
