"""POST /compress-img, /compress-pdf, /pdf-to-img, /img-to-pdf."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from app.config import get_settings
from app.services.image_compress import (
    CONVERT_FORMATS,
    OUTPUT_FORMATS,
    compress_to_buffer,
    convert_to_buffer,
    normalize_image_format,
)
from app.services.images_to_pdf import images_bytes_to_pdf
from app.services.pdf_merge import merge_pdf_bytes
from app.services.pdf_compress import compress_pdf_bytes
from app.services.pdf_to_images import PDF_TO_IMAGE_FORMATS, pdf_bytes_to_images_zip
from app.services.pdf_split_reorder import (
    build_range_pdf,
    build_reordered_pdf,
    build_split_zip,
    get_pdf_page_count,
    parse_block_order_json,
    parse_page_order_json,
    parse_single_range,
    parse_split_blocks_json,
    parse_split_ranges,
)
from app.services.result_store import save_result
from app.utils import (
    ALLOWED_EXTENSIONS,
    allowed_file,
    allowed_pdf_file,
    normalize_quality,
    normalize_scale_percent,
)
from app.utils.image_safe import open_uploaded_image
from app.utils.safe_errors import internal_error_message

router = APIRouter()


def _parse_bitmap_dpi(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return max(72, min(300, int(s)))
    except ValueError:
        return None


@router.post("/compress-img")
async def compress_img_post(
    image: UploadFile = File(...),
    output_format: Annotated[str, Form(alias="format")] = "jpeg",
    quality: Annotated[str, Form()] = "85",
):
    if not image.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)

    if not allowed_file(image.filename):
        return JSONResponse(
            {
                "error": f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
            },
            status_code=400,
        )

    fmt = (output_format or "jpeg").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in OUTPUT_FORMATS:
        return JSONResponse(
            {"error": "Invalid format. Use jpeg, webp, or png."},
            status_code=400,
        )

    q = normalize_quality(quality)

    try:
        raw = await image.read()
        if not raw:
            return JSONResponse({"error": "Empty file."}, status_code=400)
        im = open_uploaded_image(raw)
        buf, mimetype, ext = compress_to_buffer(im, fmt, q)
        data = buf.getvalue()
        name = f"compressed_{uuid.uuid4().hex[:8]}.{ext}"
        orig_size = len(raw)
        comp_size = len(data)
        token = save_result(
            data,
            media_type=mimetype,
            filename=name,
            kind="image",
            original_size=orig_size,
            compressed_size=comp_size,
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": mimetype,
                "original_size": orig_size,
                "compressed_size": comp_size,
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Image.DecompressionBombError:
        return JSONResponse(
            {"error": "Image is too large or too complex."},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)


@router.post("/convert-img")
async def convert_img_post(
    image: UploadFile = File(...),
    output_format: Annotated[str, Form(alias="format")] = "png",
    quality: Annotated[str, Form()] = "85",
    scale_percent: Annotated[str, Form()] = "100",
):
    if not image.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)

    if not allowed_file(image.filename):
        return JSONResponse(
            {
                "error": f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
            },
            status_code=400,
        )

    fmt = normalize_image_format(output_format or "png")
    if fmt not in CONVERT_FORMATS:
        allowed = ", ".join(sorted(CONVERT_FORMATS))
        return JSONResponse({"error": f"Invalid format. Use one of: {allowed}."}, status_code=400)

    q = normalize_quality(quality)
    sp = normalize_scale_percent(scale_percent)

    try:
        raw = await image.read()
        if not raw:
            return JSONResponse({"error": "Empty file."}, status_code=400)
        im = open_uploaded_image(raw)
        buf, mimetype, ext = convert_to_buffer(im, fmt, q, scale_percent=sp)
        data = buf.getvalue()
        name = f"converted_{uuid.uuid4().hex[:8]}.{ext}"
        orig_size = len(raw)
        out_size = len(data)
        token = save_result(
            data,
            media_type=mimetype,
            filename=name,
            kind="image",
            original_size=orig_size,
            compressed_size=out_size,
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": mimetype,
                "original_size": orig_size,
                "compressed_size": out_size,
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Image.DecompressionBombError:
        return JSONResponse(
            {"error": "Image is too large or too complex."},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)


@router.post("/compress-pdf")
async def compress_pdf_post(
    pdf: UploadFile = File(...),
    quality: Annotated[str, Form()] = "85",
    mode: Annotated[str, Form()] = "auto",
    bitmap_dpi: Annotated[str, Form()] = "",
):
    if not pdf.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)

    if not allowed_pdf_file(pdf.filename):
        return JSONResponse({"error": "Only PDF files are supported."}, status_code=400)

    q = normalize_quality(quality)
    mode_s = (mode or "auto").strip().lower()

    try:
        data = await pdf.read()
        if not data:
            return JSONResponse({"error": "Empty file."}, status_code=400)
        dpi_opt = _parse_bitmap_dpi(bitmap_dpi)
        out_bytes, effective, kept_original = compress_pdf_bytes(
            data, q, mode_s, bitmap_dpi=dpi_opt
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)

    name = f"compressed_{uuid.uuid4().hex[:8]}.pdf"
    orig_size = len(data)
    comp_size = len(out_bytes)
    token = save_result(
        out_bytes,
        media_type="application/pdf",
        filename=name,
        kind="pdf",
        original_size=orig_size,
        compressed_size=comp_size,
        pdf_mode=effective,
        kept_original=kept_original,
    )
    return JSONResponse(
        {
            "result_url": f"/r/{token}",
            "token": token,
            "filename": name,
            "media_type": "application/pdf",
            "original_size": orig_size,
            "compressed_size": comp_size,
            "pdf_mode": effective,
            "kept_original": kept_original,
        }
    )


@router.post("/pdf-to-img")
async def pdf_to_img_post(
    pdf: UploadFile = File(...),
    output_format: Annotated[str, Form(alias="format")] = "png",
    quality: Annotated[str, Form()] = "85",
    dpi: Annotated[str, Form()] = "",
):
    if not pdf.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)

    if not allowed_pdf_file(pdf.filename):
        return JSONResponse({"error": "Only PDF files are supported."}, status_code=400)

    fmt = (output_format or "png").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in PDF_TO_IMAGE_FORMATS:
        allowed = ", ".join(sorted(PDF_TO_IMAGE_FORMATS))
        return JSONResponse({"error": f"Invalid format. Use one of: {allowed}."}, status_code=400)

    q = normalize_quality(quality)
    dpi_val = _parse_bitmap_dpi(dpi) or get_settings().pdf_bitmap_dpi

    try:
        data = await pdf.read()
        if not data:
            return JSONResponse({"error": "Empty file."}, status_code=400)
        zip_bytes = pdf_bytes_to_images_zip(data, fmt, dpi_val, q)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)

    name = f"pages_{uuid.uuid4().hex[:8]}.zip"
    orig_size = len(data)
    out_size = len(zip_bytes)
    token = save_result(
        zip_bytes,
        media_type="application/zip",
        filename=name,
        kind="zip",
        original_size=orig_size,
        compressed_size=out_size,
    )
    return JSONResponse(
        {
            "result_url": f"/r/{token}",
            "token": token,
            "filename": name,
            "media_type": "application/zip",
            "original_size": orig_size,
            "compressed_size": out_size,
        }
    )


@router.post("/img-to-pdf")
async def img_to_pdf_post(
    images: Annotated[list[UploadFile], File()],
):
    if not images:
        return JSONResponse({"error": "No images provided."}, status_code=400)

    parts: list[bytes] = []
    total_in = 0
    try:
        for image in images:
            if not image.filename:
                return JSONResponse({"error": "Empty filename."}, status_code=400)
            if not allowed_file(image.filename):
                return JSONResponse(
                    {
                        "error": f'Unsupported file type. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
                    },
                    status_code=400,
                )
            raw = await image.read()
            if not raw:
                return JSONResponse({"error": "Empty file."}, status_code=400)
            total_in += len(raw)
            parts.append(raw)

        out_bytes = images_bytes_to_pdf(parts)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Image.DecompressionBombError:
        return JSONResponse(
            {"error": "Image is too large or too complex."},
            status_code=400,
        )
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)

    name = f"images_{uuid.uuid4().hex[:8]}.pdf"
    orig_size = total_in
    comp_size = len(out_bytes)
    token = save_result(
        out_bytes,
        media_type="application/pdf",
        filename=name,
        kind="pdf",
        original_size=orig_size,
        compressed_size=comp_size,
        page_count=len(parts),
    )
    return JSONResponse(
        {
            "result_url": f"/r/{token}",
            "token": token,
            "filename": name,
            "media_type": "application/pdf",
            "original_size": orig_size,
            "compressed_size": comp_size,
        }
    )


@router.post("/merge-pdf")
async def merge_pdf_post(
    pdfs: Annotated[list[UploadFile], File()],
):
    if not pdfs:
        return JSONResponse({"error": "No PDF files provided."}, status_code=400)

    parts: list[bytes] = []
    total_in = 0
    try:
        for pdf in pdfs:
            if not pdf.filename:
                return JSONResponse({"error": "Empty filename."}, status_code=400)
            if not allowed_pdf_file(pdf.filename):
                return JSONResponse({"error": "Only PDF files are supported."}, status_code=400)
            raw = await pdf.read()
            if not raw:
                return JSONResponse({"error": "Empty file."}, status_code=400)
            total_in += len(raw)
            parts.append(raw)

        out_bytes = merge_pdf_bytes(parts)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)

    name = f"merged_{uuid.uuid4().hex[:8]}.pdf"
    out_size = len(out_bytes)
    token = save_result(
        out_bytes,
        media_type="application/pdf",
        filename=name,
        kind="pdf",
        original_size=total_in,
        compressed_size=out_size,
        page_count=len(parts),
    )
    return JSONResponse(
        {
            "result_url": f"/r/{token}",
            "token": token,
            "filename": name,
            "media_type": "application/pdf",
            "original_size": total_in,
            "compressed_size": out_size,
        }
    )


@router.post("/split-reorder-pdf")
async def split_reorder_pdf_post(
    pdf: UploadFile = File(...),
    split_ranges: Annotated[str, Form()] = "",
    split_blocks_json: Annotated[str, Form()] = "",
    page_order_json: Annotated[str, Form()] = "",
    block_order_json: Annotated[str, Form()] = "",
    export_mode: Annotated[str, Form()] = "",
):
    if not pdf.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)
    if not allowed_pdf_file(pdf.filename):
        return JSONResponse({"error": "Only PDF files are supported."}, status_code=400)

    try:
        raw = await pdf.read()
        if not raw:
            return JSONResponse({"error": "Empty file."}, status_code=400)

        page_count = get_pdf_page_count(raw)
        page_order = parse_page_order_json(page_order_json, page_count)

        split_blocks = parse_split_blocks_json(split_blocks_json, page_count)
        if not split_blocks and (split_ranges or "").strip():
            split_blocks = parse_split_ranges(split_ranges, page_count)

        export = (export_mode or "").strip().lower()
        if export not in ("", "single", "zip"):
            return JSONResponse(
                {"error": "Invalid export mode. Use 'single' or 'zip'."},
                status_code=400,
            )

        if split_blocks:
            block_count = len(split_blocks)
            block_order = parse_block_order_json(block_order_json, block_count)

            # Convert split blocks defined in original-page numbering into reordered space.
            # This allows the UI to reorder pages first, then split by those page identities.
            reordered_set = set(page_order)
            split_set = {p for block in split_blocks for p in block}
            if split_set != reordered_set:
                return JSONResponse(
                    {"error": "Split blocks must cover all pages exactly once."},
                    status_code=400,
                )
            if sum(len(block) for block in split_blocks) != page_count:
                return JSONResponse(
                    {"error": "Split blocks cannot include duplicate pages."},
                    status_code=400,
                )

            # Product rule: split output is always ZIP of real split PDFs.
            out_bytes = build_split_zip(raw, split_blocks, block_order)
            media_type = "application/zip"
            name = f"split_{uuid.uuid4().hex[:8]}.zip"
            kind = "zip"
        else:
            # Reorder-only flow always outputs one PDF by default.
            out_bytes = build_reordered_pdf(raw, page_order)
            media_type = "application/pdf"
            name = f"reordered_{uuid.uuid4().hex[:8]}.pdf"
            kind = "pdf"

        out_size = len(out_bytes)
        token = save_result(
            out_bytes,
            media_type=media_type,
            filename=name,
            kind=kind,
            original_size=len(raw),
            compressed_size=out_size,
            page_count=page_count,
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": media_type,
                "original_size": len(raw),
                "compressed_size": out_size,
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)


@router.post("/extract-range-pdf")
async def extract_range_pdf_post(
    pdf: UploadFile = File(...),
    page_range: Annotated[str, Form()] = "",
):
    if not pdf.filename:
        return JSONResponse({"error": "Empty filename."}, status_code=400)
    if not allowed_pdf_file(pdf.filename):
        return JSONResponse({"error": "Only PDF files are supported."}, status_code=400)

    try:
        raw = await pdf.read()
        if not raw:
            return JSONResponse({"error": "Empty file."}, status_code=400)

        page_count = get_pdf_page_count(raw)
        start, end = parse_single_range(page_range, page_count)
        out_bytes = build_range_pdf(raw, start, end)

        if start == end:
            name = f"page_{start}_{uuid.uuid4().hex[:8]}.pdf"
        else:
            name = f"range_{start}-{end}_{uuid.uuid4().hex[:8]}.pdf"

        out_size = len(out_bytes)
        token = save_result(
            out_bytes,
            media_type="application/pdf",
            filename=name,
            kind="pdf",
            original_size=len(raw),
            compressed_size=out_size,
            page_count=end - start + 1,
        )
        return JSONResponse(
            {
                "result_url": f"/r/{token}",
                "token": token,
                "filename": name,
                "media_type": "application/pdf",
                "original_size": len(raw),
                "compressed_size": out_size,
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": internal_error_message(e)}, status_code=500)
