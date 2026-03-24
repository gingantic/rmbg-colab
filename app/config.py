"""Application settings loaded from environment.

Environment variables
---------------------

**Limits (optional; defaults are safe for small deployments)**

- ``MAX_UPLOAD_BYTES`` — Max multipart body size in bytes (default: 20 MiB).
- ``MAX_IMAGE_PIXELS`` — Pillow decompression cap; also enforced after decode (default: 25_000_000).
- ``MAX_IMAGE_EDGE_PX`` — Reject images whose width or height exceeds this (default: 16384).
- ``MAX_PDF_PAGES`` — Reject PDFs with more pages than this (default: 500).
- ``PDF_BITMAP_DPI`` — Render resolution for “bitmap” PDF mode (72–300; default: 150).

**Errors**

- ``DEBUG`` — If set to ``1``, ``true``, or ``yes``, API error JSON may include **raw**
  exception messages on 5xx/503. **Unset in production** so clients do not see internals.
- ``WEBBRIA_DEBUG`` — Same behavior as ``DEBUG``. Checked only if ``DEBUG`` is not
  enabling debug mode. Use this when another service on the host already uses generic ``DEBUG``.

**Compress / convert download tokens**

- ``RESULT_TTL_HOURS`` — How long each in-memory result at ``/r/{token}`` remains available
  (default: 168). Results are not written to disk.

**Background removal**

- ``HF_TOKEN`` — Hugging Face token for RMBG-2.0 (required for that feature).
- ``RMBG_PRELOAD`` — Set to ``0`` / ``false`` / ``no`` to skip loading the model at startup.
"""

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server limits loaded from the environment and optional ``.env`` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_upload_bytes: int = Field(
        default=20 * 1024 * 1024,
        description="Maximum upload body size in bytes.",
    )
    max_image_pixels: int = Field(
        default=25_000_000,
        ge=1,
        description="Maximum decoded image pixels (decompression bomb mitigation).",
    )
    max_image_edge_px: int = Field(
        default=16_384,
        ge=1,
        description="Maximum image width or height in pixels.",
    )
    max_pdf_pages: int = Field(
        default=500,
        ge=1,
        description="Maximum number of PDF pages accepted for processing.",
    )
    pdf_bitmap_dpi: int = Field(
        default=150,
        ge=72,
        le=300,
        description="DPI for rasterizing each page in bitmap PDF mode (JPEG).",
    )
    result_ttl_hours: int = Field(
        default=168,
        ge=1,
        description="In-memory compress outputs under /r/{token} expire after this many hours.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def expose_error_details() -> bool:
    """Return True if API responses may include raw exception text (debug mode).

    Reads the environment at call time (not cached on ``Settings``) so tests can toggle behavior.

    **``DEBUG``** — Preferred. Values that enable debug: ``1``, ``true``, ``yes`` (case-insensitive).

    **``WEBBRIA_DEBUG``** — Same values. Used only when ``DEBUG`` is not set or does not enable
    debug, so you can avoid clashing with another process that defines a generic ``DEBUG`` flag.
    """
    for key in ("DEBUG", "WEBBRIA_DEBUG"):
        val = os.environ.get(key, "").strip().lower()
        if val in ("1", "true", "yes"):
            return True
    return False


def should_preload_rmbg() -> bool:
    """Return True to start background RMBG model load when ``HF_TOKEN`` is set."""
    if os.environ.get("RMBG_PRELOAD", "1").lower() in ("0", "false", "no"):
        return False
    return bool(os.environ.get("HF_TOKEN"))
