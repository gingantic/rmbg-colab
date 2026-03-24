ALLOWED_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "jpe", "jfif", "webp", "bmp", "tiff"})
ALLOWED_PDF_EXTENSIONS = frozenset({"pdf"})


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_pdf_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PDF_EXTENSIONS
