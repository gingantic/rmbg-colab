"""Temporary URLs for compressed outputs: GET /r/{token}."""

from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.services.result_store import get_result_bytes, is_valid_token

router = APIRouter()


@router.get("/r/{token}")
async def result_file(token: str):
    if not is_valid_token(token):
        return JSONResponse({"error": "Not found."}, status_code=404)
    loaded = get_result_bytes(token)
    if not loaded:
        return JSONResponse({"error": "Not found or expired."}, status_code=404)
    data, meta = loaded
    filename = str(meta.get("filename") or "download")
    media_type = str(meta.get("media_type") or "application/octet-stream")
    disp = f'inline; filename="{quote(filename)}"'
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disp},
    )
