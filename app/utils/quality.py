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


def normalize_upscale_factor(raw) -> int:
    """Clamp upscale factor to 2-4 (supported factors: 2, 3, 4)."""
    try:
        scale = int(raw)
    except (TypeError, ValueError):
        return 4
    if scale not in (2, 3, 4):
        return 4
    return scale
