"""POST /remove-bg — single or bulk background removal."""

import asyncio
import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image

from app.config import expose_error_details
from app.services.rmbg import remove_background
from app.services.result_store import save_result
from app.utils import ALLOWED_EXTENSIONS, allowed_file
from app.utils.image_safe import open_uploaded_image
from app.utils.safe_errors import internal_error_message

router = APIRouter()
_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _run_rmbg_from_bytes(raw: bytes) -> bytes:
    """Decode, infer, encode — must run in a thread pool (blocks on CPU/GPU)."""
    im = open_uploaded_image(raw)
    result = remove_background(im)
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def _safe_output_stem(filename: str, fallback_index: int) -> str:
    stem = Path(filename).stem.strip()
    stem = _SAFE_STEM_RE.sub("_", stem).strip("._")
    return stem or f"image_{fallback_index}"


def _build_rmbg_zip(items: list[tuple[str, bytes]]) -> bytes:
    zip_buf = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, (filename, raw) in enumerate(items, start=1):
            out = _run_rmbg_from_bytes(raw)
            stem = _safe_output_stem(filename, idx)
            name = f"{stem}.png"
            suffix = 2
            while name in used_names:
                name = f"{stem}_{suffix}.png"
                suffix += 1
            used_names.add(name)
            zf.writestr(name, out)
    return zip_buf.getvalue()


@router.post("/remove-bg")
async def remove_bg(
    image: Annotated[UploadFile | None, File()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
):
    uploads: list[UploadFile] = []
    if image is not None:
        uploads.append(image)
    if images:
        uploads.extend(images)
    if not uploads:
        return JSONResponse({"error": "No images provided."}, status_code=400)

    try:
        parts: list[tuple[str, bytes]] = []
        total_in = 0
        for idx, upload in enumerate(uploads, start=1):
            if not upload.filename:
                return JSONResponse({"error": "Empty filename."}, status_code=400)
            if not allowed_file(upload.filename):
                return JSONResponse(
                    {
                        "error": (
                            f'Unsupported file type for "{upload.filename}". '
                            f'Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
                        ),
                    },
                    status_code=400,
                )

            raw = await upload.read()
            if not raw:
                return JSONResponse(
                    {"error": f'Empty file: "{upload.filename}".'},
                    status_code=400,
                )
            total_in += len(raw)
            parts.append((upload.filename or f"image_{idx}", raw))

        if len(parts) == 1:
            out = await asyncio.to_thread(_run_rmbg_from_bytes, parts[0][1])
            name = f"rmbg_{uuid.uuid4().hex[:8]}.png"
            return Response(
                content=out,
                media_type="image/png",
                headers={"Content-Disposition": f'inline; filename="{name}"'},
            )

        zip_bytes = await asyncio.to_thread(_build_rmbg_zip, parts)
        name = f"rmbg_batch_{uuid.uuid4().hex[:8]}.zip"
        token = save_result(
            zip_bytes,
            media_type="application/zip",
            filename=name,
            kind="zip",
            original_size=total_in,
            compressed_size=len(zip_bytes),
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": "application/zip",
                "file_count": len(parts),
                "original_size": total_in,
                "compressed_size": len(zip_bytes),
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Image.DecompressionBombError:
        return JSONResponse(
            {"error": "Image is too large or too complex."},
            status_code=400,
        )
    except RuntimeError as e:
        msg = str(e) if expose_error_details() else "Background removal is not available."
        return JSONResponse({"error": msg}, status_code=503)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)
