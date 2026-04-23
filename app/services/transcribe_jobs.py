"""In-memory async jobs for long-running audio transcription."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import time
import uuid
from typing import Any, BinaryIO

from app.services.audio_transcribe import transcribe_audio_file
from app.config import get_settings
from app.services.result_store import save_result

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _job_ttl_seconds() -> float:
    # Keep job metadata around for the same TTL as downloadable results.
    return float(get_settings().result_ttl_hours) * 3600.0


def _prune_jobs_locked() -> None:
    cutoff = _now() - _job_ttl_seconds()
    expired: list[str] = []
    for jid, job in _JOBS.items():
        if job.get("status") not in {"succeeded", "failed"}:
            continue
        finished_at = float(job.get("finished_at") or 0)
        if finished_at and finished_at < cutoff:
            expired.append(jid)
    for jid in expired:
        _JOBS.pop(jid, None)


def _serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "output_format": job["output_format"],
    }
    if job.get("error"):
        data["error"] = job["error"]
    if job.get("result"):
        data["result"] = job["result"]
    return data


def _set_job(job_id: str, **patch: Any) -> None:
    with _LOCK:
        _prune_jobs_locked()
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(patch)


def _run_job(job_id: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return
    _set_job(job_id, status="running", started_at=_now())
    temp_path = str(job["temp_audio_path"])
    try:
        media_type, ext, payload = transcribe_audio_file(
            temp_path,
            filename=job.get("filename"),
            output_format=job["output_format"],
            language_hint=job.get("language_hint"),
        )
        if ext == "json":
            result_payload = {
                "output_format": "json",
                "payload": payload,
            }
        else:
            assert isinstance(payload, bytes)
            out_name = f"transcript_{uuid.uuid4().hex[:8]}.{ext}"
            token = save_result(
                payload,
                media_type=media_type,
                filename=out_name,
                kind="transcript",
                original_size=int(job["original_size"]),
                compressed_size=len(payload),
            )
            result_payload = {
                "output_format": ext,
                "result_url": f"/r/{token}",
                "token": token,
                "filename": out_name,
                "media_type": media_type,
                "original_size": int(job["original_size"]),
                "compressed_size": len(payload),
            }
        _set_job(
            job_id,
            status="succeeded",
            finished_at=_now(),
            result=result_payload,
            error=None,
            temp_audio_path=None,
        )
    except Exception as exc:
        _set_job(
            job_id,
            status="failed",
            finished_at=_now(),
            error=str(exc),
            temp_audio_path=None,
        )
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _create_transcribe_job_from_tempfile(
    temp_path: str,
    *,
    original_size: int,
    filename: str | None,
    output_format: str,
    language_hint: str | None,
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "filename": filename,
        "temp_audio_path": temp_path,
        "original_size": original_size,
        "output_format": output_format,
        "language_hint": (language_hint or "").strip() or None,
        "result": None,
        "error": None,
    }
    with _LOCK:
        _prune_jobs_locked()
        _JOBS[job_id] = job

    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()
    return _serialize_job(job)


def create_transcribe_job(
    audio_bytes: bytes,
    *,
    filename: str | None,
    output_format: str,
    language_hint: str | None,
) -> dict[str, Any]:
    if not audio_bytes:
        raise ValueError("Empty file.")

    suffix = Path(filename or "audio.wav").suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.flush()
    finally:
        tmp.close()

    return _create_transcribe_job_from_tempfile(
        tmp.name,
        original_size=len(audio_bytes),
        filename=filename,
        output_format=output_format,
        language_hint=language_hint,
    )


def create_transcribe_job_from_stream(
    audio_stream: BinaryIO,
    *,
    filename: str | None,
    output_format: str,
    language_hint: str | None,
    chunk_size: int = 1024 * 1024,
) -> dict[str, Any]:
    suffix = Path(filename or "audio.wav").suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    total = 0
    try:
        while True:
            chunk = audio_stream.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            tmp.write(chunk)
        tmp.flush()
    finally:
        tmp.close()
    if total <= 0:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise ValueError("Empty file.")
    return _create_transcribe_job_from_tempfile(
        tmp.name,
        original_size=total,
        filename=filename,
        output_format=output_format,
        language_hint=language_hint,
    )


def get_transcribe_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        _prune_jobs_locked()
        job = _JOBS.get(job_id)
        if not job:
            return None
        return _serialize_job(job)

