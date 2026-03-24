"""Image compression (Pillow)."""

import io
from collections.abc import Mapping

from PIL import Image

from app.utils.image_safe import ensure_image_within_limits
from app.utils.quality import normalize_quality, normalize_scale_percent

OUTPUT_FORMATS = frozenset({"jpeg", "webp", "png"})
CONVERT_FORMATS = frozenset({"jpeg", "webp", "png", "gif", "bmp", "tiff"})

_FORMAT_META: Mapping[str, tuple[str, str, str]] = {
    "jpeg": ("JPEG", "image/jpeg", "jpg"),
    "webp": ("WEBP", "image/webp", "webp"),
    "png": ("PNG", "image/png", "png"),
    "gif": ("GIF", "image/gif", "gif"),
    "bmp": ("BMP", "image/bmp", "bmp"),
    "tiff": ("TIFF", "image/tiff", "tiff"),
}


def _rgba_to_rgb_white(image: Image.Image) -> Image.Image:
    if image.mode == "LA":
        image = image.convert("RGBA")
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[3])
        return bg
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def compress_to_buffer(image: Image.Image, fmt: str, quality: int) -> tuple:
    """Encode image to BytesIO; return (buffer, mimetype, filename_suffix)."""
    quality = normalize_quality(quality)
    buf = io.BytesIO()

    if fmt == "jpeg":
        rgb = _rgba_to_rgb_white(image)
        rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf, "image/jpeg", "jpg"

    if fmt == "webp":
        im = image
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        im.save(buf, format="WEBP", quality=quality, method=6)
        return buf, "image/webp", "webp"

    if fmt == "png":
        im = image
        if im.mode == "P":
            im = im.convert("RGBA")
        compress_level = max(0, min(9, int(round((quality - 1) / 99 * 9))))
        im.save(buf, format="PNG", optimize=True, compress_level=compress_level)
        return buf, "image/png", "png"

    raise ValueError("Unsupported output format")


def normalize_image_format(raw: str) -> str:
    fmt = (raw or "").strip().lower()
    if fmt == "jpg":
        return "jpeg"
    if fmt in ("tif",):
        return "tiff"
    return fmt


def _is_pillow_save_supported(pillow_fmt: str) -> bool:
    # Pillow stores encoders by canonical format key, e.g. "JPEG", "WEBP".
    return pillow_fmt.upper() in Image.SAVE


def apply_resolution_percent(image: Image.Image, percent: int) -> Image.Image:
    """Resize by width/height percentage (100 = unchanged). Uses high-quality downsampling."""
    p = normalize_scale_percent(percent)
    if p >= 100:
        return image
    w, h = image.size
    new_w = max(1, round(w * p / 100))
    new_h = max(1, round(h * p / 100))
    if new_w == w and new_h == h:
        return image
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]
    return image.resize((new_w, new_h), resample)


def convert_to_buffer(
    image: Image.Image,
    fmt: str,
    quality: int = 85,
    *,
    scale_percent: int | str = 100,
) -> tuple:
    """Convert image to a requested format; return (buffer, mimetype, ext)."""
    normalized = normalize_image_format(fmt)
    if normalized not in CONVERT_FORMATS:
        allowed = ", ".join(sorted(CONVERT_FORMATS))
        raise ValueError(f"Invalid format. Use one of: {allowed}.")

    im = apply_resolution_percent(image, normalize_scale_percent(scale_percent))
    ensure_image_within_limits(im)

    pillow_fmt, mimetype, ext = _FORMAT_META[normalized]
    if not _is_pillow_save_supported(pillow_fmt):
        raise ValueError(f"Output format '{normalized}' is not supported on this server.")

    # Reuse existing optimized compressor paths for the formats it already handles.
    if normalized in OUTPUT_FORMATS:
        return compress_to_buffer(im, normalized, quality)

    _ = normalize_quality(quality)
    buf = io.BytesIO()
    try:
        if normalized == "gif":
            gif_im = im.convert("P", palette=Image.Palette.ADAPTIVE)
            gif_im.save(buf, format="GIF", optimize=True)
            return buf, mimetype, ext

        if normalized == "bmp":
            bmp_im = im
            if bmp_im.mode not in ("RGB", "RGBA"):
                bmp_im = bmp_im.convert("RGB")
            bmp_im.save(buf, format="BMP")
            return buf, mimetype, ext

        if normalized == "tiff":
            tiff_im = im
            if tiff_im.mode == "P":
                tiff_im = tiff_im.convert("RGBA")
            # Use Deflate to keep TIFF output from ballooning for common sources.
            tiff_im.save(buf, format="TIFF", compression="tiff_deflate")
            return buf, mimetype, ext
    except (OSError, ValueError) as exc:
        raise ValueError(f"Failed to encode '{normalized}': {exc}") from exc

    raise ValueError("Unsupported output format")
