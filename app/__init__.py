"""FastAPI application package."""

from contextlib import asynccontextmanager
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app.config import get_settings, should_preload_rmbg
from app.routers import compress, pages, results, rmbg
from app.services.rmbg import ensure_rmbg_loaded


class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies when Content-Length is present (multipart uploads)."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if request.method in ("POST", "PUT", "PATCH"):
            cl = request.headers.get("content-length")
            if cl:
                try:
                    if int(cl) > settings.max_upload_bytes:
                        mb = settings.max_upload_bytes // (1024 * 1024)
                        return JSONResponse(
                            {"error": f"File too large (max {mb} MB)."},
                            status_code=413,
                        )
                except ValueError:
                    pass
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if should_preload_rmbg():
        threading.Thread(target=ensure_rmbg_loaded, daemon=True).start()
    yield


def create_app() -> FastAPI:
    load_dotenv()
    from PIL import Image as PILImage

    PILImage.MAX_IMAGE_PIXELS = get_settings().max_image_pixels
    application = FastAPI(lifespan=lifespan)

    root = Path(__file__).resolve().parent.parent
    application.mount("/static", StaticFiles(directory=str(root / "static")), name="static")

    application.add_middleware(LimitUploadSizeMiddleware)

    application.include_router(pages.router)
    application.include_router(rmbg.router)
    application.include_router(compress.router)
    application.include_router(results.router)

    return application
