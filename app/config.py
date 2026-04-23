"""Application settings loaded from environment.

Environment variables
---------------------

**Limits (optional; defaults are safe for small deployments)**

- ``MAX_UPLOAD_BYTES`` — Max multipart body size in bytes (default: 1 GiB).
- ``MAX_IMAGE_PIXELS`` — Pillow decompression cap; also enforced after decode (default: 25_000_000).
- ``MAX_IMAGE_EDGE_PX`` — Reject images whose width or height exceeds this (default: 16384).
- ``MAX_PDF_PAGES`` — Reject PDFs with more pages than this (default: 500).
- ``PDF_BITMAP_DPI`` — Render resolution for “bitmap” PDF mode (72–300; default: 150).

**Errors**

- ``DEBUG`` — If set to ``1``, ``true``, or ``yes``, API error JSON may include **raw**
  exception messages on 5xx/503. **Unset in production** so clients do not see internals.

**Compress / convert download tokens**

- ``RESULT_TTL_HOURS`` — How long each in-memory result at ``/r/{token}`` remains available
  (default: 168). Results are not written to disk.

**Background removal**

- ``HF_TOKEN`` — Hugging Face token for RMBG-2.0 (required for that feature).
- ``RMBG_PRELOAD`` — Set to ``1`` / ``true`` / ``yes`` to preload the model at startup
  (default: disabled).

**Image upscaler**

- ``UPSCALER_MODELS_DIR`` — Directory used to cache Real-ESRGAN checkpoints
  (default: ``.cache/upscaler-models``).
- ``UPSCALER_MAX_OUTPUT_EDGE_PX`` — Max width/height allowed after upscale (default: 8192).
- ``UPSCALER_PRELOAD`` — Set to ``1`` / ``true`` / ``yes`` to preload upscaler models at startup.

**Audio transcription + diarization**

- ``TRANSCRIBE_ASR_MODEL`` — ASR model for WhisperX/faster-whisper (default: ``large-v3``).
- ``TRANSCRIBE_DEVICE`` — ``auto``, ``cpu``, or ``cuda`` (default: ``auto``).
- ``TRANSCRIBE_COMPUTE_TYPE`` — ``auto`` (recommended), or runtime-specific values like
  ``float16``/``int8``.
- ``TRANSCRIBE_BATCH_SIZE`` — Whisper inference batch size (default: 16).
- ``TRANSCRIBE_LANGUAGE_HINT`` — Default ASR language (e.g. ``id``). Set empty for auto-detect.
  Also passed to WhisperX at model load (avoids a misleading no-language log at startup).
- ``TRANSCRIBE_BEAM_SIZE`` — Beam size for decoding (default: 5). Higher can improve accuracy.
- ``TRANSCRIBE_BEST_OF`` — Number of candidate decodes sampled per segment (default: 5).
- ``TRANSCRIBE_INITIAL_PROMPT`` — Optional decoding prompt to bias colloquial/code-switched speech.
- ``TRANSCRIBE_CONDITION_ON_PREV_TEXT`` — ``1``/``true``/``yes`` to condition on prior segment text.
- ``TRANSCRIBE_DIARIZATION_MODEL`` — pyannote diarization pipeline
  (default: ``pyannote/speaker-diarization-3.1``).
- ``HF_TOKEN`` — Hugging Face token for pyannote diarization model access.
- ``TRANSCRIBE_PRELOAD`` — Set to ``1`` / ``true`` / ``yes`` to preload/download
  ASR + diarization models at startup (default: disabled).
- ``HF_VERIFY_GATED_ACCESS`` — Set to ``0`` / ``false`` / ``no`` to skip proactive
  Hugging Face gated-access agreement checks before model load.
"""

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server limits loaded from the environment and optional ``.env`` file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_upload_bytes: int = Field(
        default=1024 * 1024 * 1024,
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
    upscaler_models_dir: str = Field(
        default=".cache/upscaler-models",
        description="Directory for local upscaler checkpoint cache.",
    )
    upscaler_max_output_edge_px: int = Field(
        default=8192,
        ge=1,
        description="Maximum width or height allowed for upscaled output images.",
    )
    hf_token: str | None = Field(
        default=None,
        description="Hugging Face token used by gated models (RMBG and diarization).",
    )
    transcribe_asr_model: str = Field(
        default="large-v3",
        description="High-accuracy multilingual Whisper model used by whisperx/faster-whisper.",
    )
    transcribe_device: str = Field(
        default="auto",
        description="Transcription inference device: auto, cpu, or cuda.",
    )
    transcribe_compute_type: str = Field(
        default="auto",
        description="Compute precision for faster-whisper runtime.",
    )
    transcribe_batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Batch size for ASR transcription pass.",
    )
    transcribe_language_hint: str = Field(
        default="",
        description="Default ASR language hint. Empty string = auto-detect.",
    )
    transcribe_beam_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Beam size for ASR decoding; higher can improve noisy/colloquial speech.",
    )
    transcribe_best_of: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Best-of candidates for decoding; higher may improve recognition quality.",
    )
    transcribe_initial_prompt: str = Field(
        default=(
            "Natural conversational speech, including slang, filler words, and "
            "code-switching between Indonesian and English."
        ),
        description="Optional ASR initial prompt to improve casual/code-switched transcription.",
    )
    transcribe_condition_on_prev_text: bool = Field(
        default=True,
        description="Condition decoding on previous segment text for continuity.",
    )
    transcribe_diarization_model: str = Field(
        default="pyannote/speaker-diarization-3.1",
        description="High-accuracy Hugging Face model id for pyannote diarization pipeline.",
    )
    transcribe_preload: bool = Field(
        default=False,
        description="Preload/download transcription models during application startup.",
    )
    hf_verify_gated_access: bool = Field(
        default=True,
        description="Verify gated Hugging Face model access (token + agreement) before load.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def expose_error_details() -> bool:
    """Return True if API responses may include raw exception text (debug mode).

    Reads the environment at call time (not cached on ``Settings``) so tests can toggle behavior.

    **``DEBUG``** — Preferred. Values that enable debug: ``1``, ``true``, ``yes`` (case-insensitive).

    """
    for key in ("DEBUG"):
        val = os.environ.get(key, "").strip().lower()
        if val in ("1", "true", "yes"):
            return True
    return False


def should_preload_rmbg() -> bool:
    """Return True to start background RMBG model load when ``HF_TOKEN`` is set."""
    return os.environ.get("RMBG_PRELOAD", "0").lower() in ("1", "true", "yes") and bool(
        os.environ.get("HF_TOKEN")
    )


def should_preload_upscaler() -> bool:
    """Return True if upscaler models should preload during startup."""
    return os.environ.get("UPSCALER_PRELOAD", "0").lower() in ("1", "true", "yes")


def should_preload_transcribe() -> bool:
    """Return True if transcription models should preload during startup."""
    return os.environ.get("TRANSCRIBE_PRELOAD", "0").lower() in ("1", "true", "yes")
