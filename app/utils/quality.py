def normalize_quality(raw) -> int:
    try:
        q = int(raw)
    except (TypeError, ValueError):
        return 85
    return max(1, min(100, q))


def normalize_scale_percent(raw) -> int:
    """Clamp resolution scale to 1–100 (100 = original width/height)."""
    try:
        q = int(raw)
    except (TypeError, ValueError):
        return 100
    return max(1, min(100, q))
