"""POST /transcribe-audio for batch transcription + diarization."""

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.audio_transcribe import normalize_export_format, transcribe_audio_bytes
from app.services.transcribe_jobs import create_transcribe_job_from_stream, get_transcribe_job
from app.services.result_store import save_result
from app.utils.safe_errors import internal_error_message

router = APIRouter()


@router.post("/transcribe-audio")
async def transcribe_audio_post(
    audio: UploadFile = File(...),
    output_format: Annotated[str, Form(alias="format")] = "json",
    language_hint: Annotated[str, Form()] = "",
):
    if not audio.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)
    try:
        raw = await audio.read()
        media_type, ext, payload = await asyncio.to_thread(
            transcribe_audio_bytes,
            raw,
            filename=audio.filename,
            output_format=output_format,
            language_hint=language_hint,
        )
        if ext == "json":
            return JSONResponse(payload)

        assert isinstance(payload, bytes)
        name = f"transcript_{uuid.uuid4().hex[:8]}.{ext}"
        token = save_result(
            payload,
            media_type=media_type,
            filename=name,
            kind="transcript",
            original_size=len(raw),
            compressed_size=len(payload),
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": media_type,
                "original_size": len(raw),
                "compressed_size": len(payload),
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)


@router.post("/transcribe-audio/async")
async def transcribe_audio_async_post(
    audio: UploadFile = File(...),
    output_format: Annotated[str, Form(alias="format")] = "json",
    language_hint: Annotated[str, Form()] = "",
):
    if not audio.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)
    try:
        fmt = normalize_export_format(output_format)
        await audio.seek(0)
        job = await asyncio.to_thread(
            create_transcribe_job_from_stream,
            audio.file,
            filename=audio.filename,
            output_format=fmt,
            language_hint=language_hint,
        )
        return JSONResponse(
            {
                "message": "Job accepted. Poll status endpoint until finished.",
                "job_id": job["job_id"],
                "status": job["status"],
                "status_url": f"/transcribe-audio/jobs/{job['job_id']}",
            },
            status_code=202,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)


@router.get("/transcribe-audio/jobs/{job_id}")
@router.get("/transcribe-audio/jobs/{job_id}/stream")
async def transcribe_audio_job_status(job_id: str, request: Request):
    job = get_transcribe_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found."}, status_code=404)

    if not request.url.path.endswith("/stream"):
        return JSONResponse(job)

    async def stream():
        last_payload = ""
        while True:
            if await request.is_disconnected():
                break
            current = get_transcribe_job(job_id)
            if current is None:
                yield "data: " + json.dumps({"status": "failed", "error": "Job not found."}) + "\n\n"
                break

            payload = json.dumps(current, separators=(",", ":"))
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            else:
                # Comment frame keeps intermediaries from idling out the stream.
                yield ": keep-alive\n\n"

            if current.get("status") in {"succeeded", "failed"}:
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
