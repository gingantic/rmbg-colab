"""HTML pages (GET)."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.dependencies import get_templates

router = APIRouter()
templates = get_templates()


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


_PAGE = {
    "rmbg": {
        "full": "index.html",
        "fragment": "htmx/rmbg.html",
        "page_title": "RMBG 2.0 — AI Background Remover",
        "tagline": "AI-Powered Background Removal",
        "badge": "RMBG",
    },
    "compress_img": {
        "full": "compress_img.html",
        "fragment": "htmx/compress_img.html",
        "page_title": "Image Compressor",
        "tagline": "Smaller files, same pixels",
        "badge": "Compress",
    },
    "convert_img": {
        "full": "convert_img.html",
        "fragment": "htmx/convert_img.html",
        "page_title": "Image Converter",
        "tagline": "Switch formats in one click",
        "badge": "Convert",
    },
    "compress_pdf": {
        "full": "compress_pdf.html",
        "fragment": "htmx/compress_pdf.html",
        "page_title": "PDF Compressor",
        "tagline": "Structure-aware, not flattened",
        "badge": "PDF",
    },
    "pdf_to_img": {
        "full": "pdf_to_img.html",
        "fragment": "htmx/pdf_to_img.html",
        "page_title": "PDF to images",
        "tagline": "Each page as an image in a ZIP",
        "badge": "PDF",
    },
    "img_to_pdf": {
        "full": "img_to_pdf.html",
        "fragment": "htmx/img_to_pdf.html",
        "page_title": "Images to PDF",
        "tagline": "Stack images into one document",
        "badge": "PDF",
    },
    "merge_pdf": {
        "full": "merge_pdf.html",
        "fragment": "htmx/merge_pdf.html",
        "page_title": "Merge PDF",
        "tagline": "Combine multiple PDFs in custom order",
        "badge": "PDF",
    },
    "split_reorder_pdf": {
        "full": "split_reorder_pdf.html",
        "fragment": "htmx/split_reorder_pdf.html",
        "page_title": "Split + Reorder PDF",
        "tagline": "Split one PDF and reorder blocks or pages",
        "badge": "PDF",
    },
    "extract_range_pdf": {
        "full": "extract_range_pdf.html",
        "fragment": "htmx/extract_range_pdf.html",
        "page_title": "Extract PDF Pages",
        "tagline": "Keep only a page range",
        "badge": "PDF",
    },
}


def _render_page(request: Request, key: str):
    meta = _PAGE[key]
    ctx = {
        "active_page": key,
        "page_title": meta["page_title"],
        "tagline": meta["tagline"],
        "badge": meta["badge"],
    }
    name = meta["fragment"] if _is_htmx(request) else meta["full"]
    return templates.TemplateResponse(request, name, ctx)


@router.get("/", name="index")
async def index(request: Request):
    return _render_page(request, "rmbg")


@router.get("/compress", name="compress_legacy")
async def compress_legacy_redirect():
    """Old path / bookmark / history entry — PDF compressor lives at /compress-pdf."""
    return RedirectResponse(url="/compress-pdf", status_code=301)


@router.get("/compress-img", name="compress_img")
async def compress_img_page(request: Request):
    return _render_page(request, "compress_img")


@router.get("/convert-img", name="convert_img")
async def convert_img_page(request: Request):
    return _render_page(request, "convert_img")


@router.get("/compress-pdf", name="compress_pdf")
async def compress_pdf_page(request: Request):
    return _render_page(request, "compress_pdf")


@router.get("/pdf-to-img", name="pdf_to_img")
async def pdf_to_img_page(request: Request):
    return _render_page(request, "pdf_to_img")


@router.get("/img-to-pdf", name="img_to_pdf")
async def img_to_pdf_page(request: Request):
    return _render_page(request, "img_to_pdf")


@router.get("/merge-pdf", name="merge_pdf")
async def merge_pdf_page(request: Request):
    return _render_page(request, "merge_pdf")


@router.get("/split-reorder-pdf", name="split_reorder_pdf")
async def split_reorder_pdf_page(request: Request):
    return _render_page(request, "split_reorder_pdf")


@router.get("/extract-range-pdf", name="extract_range_pdf")
async def extract_range_pdf_page(request: Request):
    return _render_page(request, "extract_range_pdf")
