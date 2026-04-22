"""Batch audio transcription + speaker diarization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import tempfile
import threading
from typing import Any

from app.config import get_settings
from app.schemas.transcribe import TranscribeResult, TranscriptSegment, TranscriptWord

SUPPORTED_EXPORT_FORMATS = frozenset({"json", "srt", "vtt"})
SUPPORTED_AUDIO_EXTS = frozenset(
    {
        ".wav",
        ".mp3",
        ".m4a",
        ".flac",
        ".ogg",
        ".opus",
        ".webm",
        ".mp4",
        ".aac",
        ".wma",
    }
)

_RUNTIME_LOCK = threading.Lock()
_RUNTIME: "_TranscribeRuntime | None" = None
_LANGUAGE_HINT_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z]{2,4})?$", re.IGNORECASE)


@dataclass
class _TranscribeRuntime:
    whisperx: Any
    asr_model: Any
    diarization_pipeline: Any
    device: str
    align_cache: dict[str, tuple[Any, Any]]


def _normalize_export_format(value: str | None) -> str:
    fmt = (value or "json").strip().lower()
    if fmt not in SUPPORTED_EXPORT_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_EXPORT_FORMATS))
        raise ValueError(f"Invalid format. Use one of: {allowed}.")
    return fmt


def normalize_export_format(value: str | None) -> str:
    """Public wrapper used by routers/job orchestration."""
    return _normalize_export_format(value)


def _resolve_device() -> str:
    configured = (get_settings().transcribe_device or "auto").strip().lower()
    if configured in {"cpu", "cuda"}:
        return configured
    try:
        import torch
    except Exception:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_compute_type(device: str) -> str:
    configured = (get_settings().transcribe_compute_type or "auto").strip().lower()
    if configured != "auto":
        return configured
    return "float16" if device == "cuda" else "int8"


def _resolve_hf_token() -> str:
    settings = get_settings()
    token = (settings.hf_token or os.environ.get("HF_TOKEN") or "").strip()
    if token:
        return token
    raise ValueError(
        "Missing Hugging Face token for diarization. Set HF_TOKEN."
    )


def _effective_language(language_hint: str | None) -> str | None:
    """Validate request language hint; empty/invalid means auto-detect."""
    candidate = (language_hint or "").strip()
    if not candidate:
        return None
    # Guard against accidental numeric/invalid form values (e.g. "50360")
    # that can confuse tokenizer task/language selection downstream.
    if _LANGUAGE_HINT_RE.match(candidate):
        return candidate.lower()
    return None


def _build_asr_options() -> dict[str, Any]:
    settings = get_settings()
    options: dict[str, Any] = {
        "beam_size": settings.transcribe_beam_size,
        "best_of": settings.transcribe_best_of,
        "condition_on_previous_text": settings.transcribe_condition_on_prev_text,
    }
    initial_prompt = (settings.transcribe_initial_prompt or "").strip()
    if initial_prompt:
        options["initial_prompt"] = initial_prompt
    return options


def _ensure_runtime() -> _TranscribeRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            return _RUNTIME
        try:
            import whisperx
            from whisperx.diarize import DiarizationPipeline
        except Exception as exc:
            raise ValueError(
                "Transcription runtime is unavailable. Install whisperx and pyannote.audio dependencies."
            ) from exc

        settings = get_settings()
        device = _resolve_device()
        compute_type = _resolve_compute_type(device)
        asr_model = whisperx.load_model(
            settings.transcribe_asr_model,
            device,
            compute_type=compute_type,
            asr_options=_build_asr_options(),
        )
        # WhisperX 3.8+ exposes DiarizationPipeline from whisperx.diarize (not whisperx top-level).
        diarization_pipeline = DiarizationPipeline(
            model_name=settings.transcribe_diarization_model,
            token=_resolve_hf_token(),
            device=device,
        )
        _RUNTIME = _TranscribeRuntime(
            whisperx=whisperx,
            asr_model=asr_model,
            diarization_pipeline=diarization_pipeline,
            device=device,
            align_cache={},
        )
        return _RUNTIME


def reset_transcribe_runtime() -> None:
    """Clear cached ASR/diarization runtime so new settings take effect."""
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = None


def _align_segments(runtime: _TranscribeRuntime, audio: Any, language: str, segments: list[dict[str, Any]]):
    if not segments:
        return segments
    if language not in runtime.align_cache:
        model_a, metadata = runtime.whisperx.load_align_model(
            language_code=language,
            device=runtime.device,
        )
        runtime.align_cache[language] = (model_a, metadata)
    align_model, metadata = runtime.align_cache[language]
    aligned = runtime.whisperx.align(
        segments,
        align_model,
        metadata,
        audio,
        runtime.device,
        return_char_alignments=False,
    )
    return aligned.get("segments", segments)


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _segment_to_schema(segment: dict[str, Any]) -> TranscriptSegment:
    words: list[TranscriptWord] = []
    for word in segment.get("words") or []:
        words.append(
            TranscriptWord(
                word=str(word.get("word") or "").strip(),
                start=_safe_float(word.get("start")),
                end=_safe_float(word.get("end")),
                confidence=_safe_float(word.get("score")),
                speaker=(word.get("speaker") or None),
            )
        )
    return TranscriptSegment(
        start=float(segment.get("start") or 0.0),
        end=float(segment.get("end") or 0.0),
        text=str(segment.get("text") or "").strip(),
        speaker=segment.get("speaker") or None,
        words=words,
    )


def _format_timestamp(seconds: float, *, vtt: bool) -> str:
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3_600_000
    rem = total_ms % 3_600_000
    minutes = rem // 60_000
    rem = rem % 60_000
    secs = rem // 1000
    ms = rem % 1000
    sep = "." if vtt else ","
    return f"{hours:02}:{minutes:02}:{secs:02}{sep}{ms:03}"


def _render_srt(segments: list[TranscriptSegment]) -> str:
    blocks: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg.start, vtt=False)
        end = _format_timestamp(max(seg.end, seg.start), vtt=False)
        text = seg.text
        if seg.speaker:
            text = f"[{seg.speaker}] {text}"
        blocks.append(f"{idx}\n{start} --> {end}\n{text}".strip())
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _render_vtt(segments: list[TranscriptSegment]) -> str:
    blocks: list[str] = ["WEBVTT\n"]
    for seg in segments:
        start = _format_timestamp(seg.start, vtt=True)
        end = _format_timestamp(max(seg.end, seg.start), vtt=True)
        text = seg.text
        if seg.speaker:
            text = f"[{seg.speaker}] {text}"
        blocks.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(blocks).strip() + "\n"


def _transcribe_json(audio_path: str, language_hint: str | None) -> TranscribeResult:
    runtime = _ensure_runtime()
    settings = get_settings()
    audio = runtime.whisperx.load_audio(audio_path)

    language_for_asr = _effective_language(language_hint) or _effective_language(
        settings.transcribe_language_hint
    )
    transcribe_kwargs: dict[str, Any] = {
        "batch_size": settings.transcribe_batch_size,
        "task": "transcribe",
    }
    if language_for_asr:
        transcribe_kwargs["language"] = language_for_asr

    result = runtime.asr_model.transcribe(audio, **transcribe_kwargs)
    language = str(result.get("language") or language_hint or "unknown")
    segments = list(result.get("segments") or [])

    try:
        segments = _align_segments(runtime, audio, language, segments)
    except Exception:
        # Keep transcription usable even when align model for this language is unavailable.
        pass

    diarization_result = runtime.diarization_pipeline(audio_path)
    assigned = runtime.whisperx.assign_word_speakers(
        diarization_result,
        {"segments": segments, "language": language},
    )
    final_segments = [_segment_to_schema(s) for s in assigned.get("segments") or []]
    speakers = sorted({seg.speaker for seg in final_segments if seg.speaker})
    return TranscribeResult(
        language=language,
        asr_model=settings.transcribe_asr_model,
        diarization_model=settings.transcribe_diarization_model,
        speakers=speakers,
        segments=final_segments,
    )


def transcribe_audio_path(audio_path: str, *, language_hint: str | None = None) -> dict[str, Any]:
    """Transcribe a local audio path and return JSON-serializable result."""
    result = _transcribe_json(audio_path, (language_hint or "").strip() or None)
    return result.model_dump()


def transcribe_audio_file(
    audio_path: str,
    *,
    filename: str | None = None,
    output_format: str = "json",
    language_hint: str | None = None,
) -> tuple[str, str, bytes | dict[str, Any]]:
    """Transcribe a local file path and render json/srt/vtt payload."""
    ext = Path(filename or audio_path or "audio.wav").suffix.lower() or ".wav"
    if ext not in SUPPORTED_AUDIO_EXTS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTS))
        raise ValueError(f"Unsupported audio type. Allowed: {allowed}.")
    fmt = _normalize_export_format(output_format)
    result = _transcribe_json(audio_path, (language_hint or "").strip() or None)
    if fmt == "json":
        return "application/json", "json", result.model_dump()
    if fmt == "srt":
        return "text/plain; charset=utf-8", "srt", _render_srt(result.segments).encode("utf-8")
    return "text/vtt; charset=utf-8", "vtt", _render_vtt(result.segments).encode("utf-8")


def transcribe_audio_bytes(
    audio_bytes: bytes,
    *,
    filename: str | None,
    output_format: str = "json",
    language_hint: str | None = None,
) -> tuple[str, str, bytes | dict[str, Any]]:
    """Return (media_type, extension, payload) for json/srt/vtt transcription output."""
    if not audio_bytes:
        raise ValueError("Empty file.")
    ext = Path(filename or "audio.wav").suffix.lower() or ".wav"
    if ext not in SUPPORTED_AUDIO_EXTS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTS))
        raise ValueError(f"Unsupported audio type. Allowed: {allowed}.")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        return transcribe_audio_file(
            tmp.name,
            filename=filename,
            output_format=output_format,
            language_hint=language_hint,
        )

