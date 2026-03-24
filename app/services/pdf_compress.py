"""PDF compression (pikepdf + pypdf heuristics)."""

import io

import img2pdf
import pikepdf
import pypdfium2 as pdfium
from pikepdf import PdfImage, Name
from pikepdf.settings import set_flate_compression_level
from PIL import Image
from pypdf import PdfReader

from app.config import get_settings
from app.utils.quality import normalize_quality

# pikepdf default Flate level is -1 (zlib default, usually ~6). Level 9 is max
# compression for deflate streams in PDF saves (more CPU, smaller files).
set_flate_compression_level(9)

# Auto mode: image-style recompression when extractable text is sparse or image streams dominate.
PDF_AVG_TEXT_LOW = 30
PDF_IMAGE_RATIO_HIGH = 0.55


def _pdf_image_object_id(img_obj) -> tuple:
    try:
        gen = img_obj.objgen
        if gen:
            return ("i", int(gen[0]), int(gen[1]))
    except (AttributeError, TypeError, ValueError):
        pass
    return ("id", id(img_obj))


def _estimate_pdf_image_raw_bytes(pdf: pikepdf.Pdf) -> int:
    seen = set()
    total = 0
    for page in pdf.pages:
        for _name, img_obj in page.images.items():
            ident = _pdf_image_object_id(img_obj)
            if ident in seen:
                continue
            seen.add(ident)
            try:
                total += len(img_obj.read_raw_bytes())
            except Exception:
                continue
    return total


def _pypdf_extract_text_length(data: bytes) -> int:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        if reader.decrypt("") == 0:
            raise ValueError(
                "This PDF is encrypted. Remove encryption or use a tool that supports passwords."
            )
    n = 0
    for page in reader.pages:
        try:
            n += len(page.extract_text() or "")
        except Exception:
            continue
    return n


def classify_pdf_mode(data: bytes, pdf: pikepdf.Pdf) -> str:
    """Return 'text' or 'image' for automatic routing."""
    text_len = _pypdf_extract_text_length(data)
    pages = max(len(pdf.pages), 1)
    avg_text = text_len / pages
    file_len = max(len(data), 1)
    image_raw = _estimate_pdf_image_raw_bytes(pdf)
    image_ratio = image_raw / file_len
    if avg_text < PDF_AVG_TEXT_LOW or image_ratio >= PDF_IMAGE_RATIO_HIGH:
        return "image"
    return "text"


def _pil_to_pdf_jpeg(pil: Image.Image, quality: int) -> tuple:
    """Return (jpeg_bytes, width, height)."""
    im = pil
    if im.mode == "P":
        im = im.convert("RGBA")
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        if im.mode == "RGBA":
            bg.paste(im, mask=im.split()[3])
        else:
            bg.paste(im.convert("RGB"))
        im = bg
    elif im.mode == "CMYK":
        im = im.convert("RGB")
    elif im.mode != "RGB":
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), im.width, im.height


def _recompress_pdf_image_object(img_obj, quality: int) -> None:
    try:
        pdfimg = PdfImage(img_obj)
    except Exception:
        return
    if pdfimg.image_mask:
        return
    if pdfimg.is_separation or pdfimg.is_device_n:
        return
    try:
        pil = pdfimg.as_pil_image()
    except Exception:
        return
    if pil.width * pil.height < 16:
        return
    try:
        jpeg_bytes, w, h = _pil_to_pdf_jpeg(pil, quality)
    except Exception:
        return
    raw = pdfimg.obj
    for key in (
        "/SMask",
        "/Mask",
        "/ImageMask",
        "/DecodeParms",
        "/Filter",
        "/ColorSpace",
        "/BitsPerComponent",
        "/Width",
        "/Height",
        "/Intent",
        "/Interpolate",
    ):
        try:
            del raw[Name(key)]
        except KeyError:
            pass
    raw.write(jpeg_bytes, filter=Name.DCTDecode)
    raw.Width = w
    raw.Height = h
    raw.ColorSpace = Name.DeviceRGB
    raw.BitsPerComponent = 8


def _recompress_all_pdf_images(pdf: pikepdf.Pdf, quality: int) -> None:
    seen = set()
    for page in pdf.pages:
        for _name, img_obj in page.images.items():
            ident = _pdf_image_object_id(img_obj)
            if ident in seen:
                continue
            seen.add(ident)
            _recompress_pdf_image_object(img_obj, quality)


def _strip_pdf_metadata(pdf: pikepdf.Pdf) -> None:
    """Remove embedded XMP/metadata catalog entry when present (often large, rarely needed)."""
    try:
        root = pdf.Root
        if Name.Metadata in root:
            del root[Name.Metadata]
    except Exception:
        pass


def _apply_pdf_mutations(pdf: pikepdf.Pdf, effective: str, quality: int) -> None:
    """Mutate in-memory PDF before save (images and/or metadata)."""
    if effective == "image":
        _recompress_all_pdf_images(pdf, quality)
    if effective == "text":
        _strip_pdf_metadata(pdf)


def _pdf_save_variant(pdf: pikepdf.Pdf, *, object_stream_mode) -> bytes:
    """
    Write with deflate recompression. linearize=False — linearization adds xref
    structure and often *increases* size (meant for byte-range web serving, not archiving).
    """
    out = io.BytesIO()
    pdf.save(
        out,
        compress_streams=True,
        object_stream_mode=object_stream_mode,
        linearize=False,
        recompress_flate=True,
        stream_decode_level=pikepdf.StreamDecodeLevel.all,
    )
    return out.getvalue()


def compress_pdf_to_bitmap(data: bytes, quality: int, dpi: int) -> bytes:
    """Render each page to a JPEG (DCT) and assemble a new PDF via img2pdf.

    Text and vectors are flattened to pixels — no selectable text. Efficient for
    maximum size reduction when that tradeoff is acceptable.
    """
    quality = normalize_quality(quality)
    dpi = max(72, min(300, int(dpi)))

    try:
        doc = pdfium.PdfDocument(io.BytesIO(data))
    except Exception as e:
        raise ValueError(
            "Could not open this PDF for rasterization (it may be encrypted or corrupted)."
        ) from e

    n = len(doc)
    max_pages = get_settings().max_pdf_pages
    if n > max_pages:
        raise ValueError(f"This PDF has too many pages (maximum {max_pages}).")
    if n < 1:
        raise ValueError("PDF has no pages.")

    max_px = get_settings().max_image_pixels
    scale = dpi / 72.0
    jpegs: list[bytes] = []

    for i in range(n):
        page = doc[i]
        pil = page.render(scale=scale).to_pil()
        if pil.mode != "RGB":
            pil = pil.convert("RGB")
        w, h = pil.size
        if w * h > max_px:
            raise ValueError(
                "A page is too large after rendering at this DPI. "
                "Lower PDF_BITMAP_DPI or use another mode."
            )
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=quality, optimize=True)
        jpegs.append(buf.getvalue())

    return img2pdf.convert(jpegs)


def compress_pdf_bytes(
    data: bytes,
    quality: int,
    mode: str,
    *,
    bitmap_dpi: int | None = None,
) -> tuple:
    """
    Compress PDF. Modes ``auto`` / ``text`` / ``image`` avoid full-page rasterization.

    Mode ``bitmap`` renders each page to a JPEG (PDFium) and rebuilds the PDF
    (img2pdf); text is not selectable.

    Returns (output_bytes, effective_mode, kept_original). If every non-bitmap
    save variant is larger than the upload, returns the original bytes and
    kept_original=True.
    """
    quality = normalize_quality(quality)
    mode = (mode or "auto").strip().lower()
    if mode not in ("auto", "text", "image", "bitmap"):
        mode = "auto"

    if mode == "bitmap":
        dpi = bitmap_dpi if bitmap_dpi is not None else get_settings().pdf_bitmap_dpi
        out = compress_pdf_to_bitmap(data, quality, dpi)
        n_in = len(data)
        kept = len(out) >= n_in
        if kept:
            out = data
        return out, "bitmap", kept

    try:
        with pikepdf.open(io.BytesIO(data)) as pdf_probe:
            max_pages = get_settings().max_pdf_pages
            if len(pdf_probe.pages) > max_pages:
                raise ValueError(
                    f"This PDF has too many pages (maximum {max_pages})."
                )
            if mode == "auto":
                effective = classify_pdf_mode(data, pdf_probe)
            else:
                effective = mode
    except pikepdf.PasswordError as e:
        raise ValueError("This PDF is password-protected. Webbria cannot decrypt it.") from e
    except pikepdf.PdfError as e:
        raise ValueError(f"Invalid or unreadable PDF: {e}") from e

    n_in = len(data)
    best: bytes | None = None
    for osm in (
        pikepdf.ObjectStreamMode.generate,
        pikepdf.ObjectStreamMode.preserve,
    ):
        try:
            pdf = pikepdf.open(io.BytesIO(data))
        except pikepdf.PdfError:
            continue
        with pdf:
            _apply_pdf_mutations(pdf, effective, quality)
            try:
                cand = _pdf_save_variant(pdf, object_stream_mode=osm)
            except pikepdf.PdfError:
                continue
        if best is None or len(cand) < len(best):
            best = cand

    if best is None:
        raise ValueError("Could not write a valid PDF after optimization.")

    kept_original = len(best) >= n_in
    if kept_original:
        out = data
    else:
        out = best

    return out, effective, kept_original
