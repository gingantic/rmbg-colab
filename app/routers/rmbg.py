"""POST /remove-bg — background removal."""

import io
import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image

from app.config import expose_error_details
from app.services.rmbg import remove_background
from app.utils import ALLOWED_EXTENSIONS, allowed_file
from app.utils.image_safe import open_uploaded_image
from app.utils.safe_errors import internal_error_message

router = APIRouter()


@router.post("/remove-bg")
async def remove_bg(image: UploadFile = File(...)):
    if not image.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)

    if not allowed_file(image.filename):
        return JSONResponse(
            {
                "error": f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
            },
            status_code=400,
        )

    try:
        raw = await image.read()
        if not raw:
            return JSONResponse({"error": "Empty file."}, status_code=400)
        im = open_uploaded_image(raw)
        result = remove_background(im)

        buf = io.BytesIO()
        result.save(buf, format="PNG")
        out = buf.getvalue()

        name = f"rmbg_{uuid.uuid4().hex[:8]}.png"
        return Response(
            content=out,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="{name}"'},
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
