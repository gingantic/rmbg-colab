"""POST compress endpoints and upload limit middleware."""

import io
import zipfile

from pypdf import PdfReader


def test_compress_img_jpeg(client, tiny_png_bytes):
    files = {"image": ("t.png", tiny_png_bytes, "image/png")}
    data = {"format": "jpeg", "quality": "85"}
    r = client.post("/compress-img", files=files, data=data)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/json"
    j = r.json()
    assert j.get("result_url", "").startswith("/r/")
    assert len(j.get("token", "")) == 32
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "image/jpeg"


def test_compress_pdf(client, minimal_pdf_bytes):
    files = {"pdf": ("t.pdf", minimal_pdf_bytes, "application/pdf")}
    data = {"quality": "85", "mode": "auto"}
    r = client.post("/compress-pdf", files=files, data=data)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/json"
    j = r.json()
    assert "pdf_mode" in j
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "application/pdf"


def test_post_too_large_returns_413(client):
    r = client.post(
        "/remove-bg",
        headers={"Content-Length": str(21 * 1024 * 1024)},
    )
    assert r.status_code == 413
    assert r.json().get("error")


def test_compress_img_rejects_bad_extension(client):
    files = {"image": ("x.exe", b"abc", "application/octet-stream")}
    data = {"format": "jpeg", "quality": "85"}
    r = client.post("/compress-img", files=files, data=data)
    assert r.status_code == 400
    assert "error" in r.json()


def test_convert_img_png(client, tiny_png_bytes):
    files = {"image": ("t.png", tiny_png_bytes, "image/png")}
    data = {"format": "gif", "quality": "85"}
    r = client.post("/convert-img", files=files, data=data)
    assert r.status_code == 200
    j = r.json()
    assert j["media_type"] == "image/gif"
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "image/gif"


def test_convert_img_invalid_format(client, tiny_png_bytes):
    files = {"image": ("t.png", tiny_png_bytes, "image/png")}
    data = {"format": "avif", "quality": "85"}
    r = client.post("/convert-img", files=files, data=data)
    assert r.status_code == 400
    assert "Invalid format" in r.json().get("error", "")


def test_convert_img_scale_percent(client, tiny_png_bytes, tmp_path, monkeypatch):
    monkeypatch.setenv("WEBBRIA_RESULTS_DIR", str(tmp_path))
    files = {"image": ("t.png", tiny_png_bytes, "image/png")}
    data = {"format": "png", "quality": "85", "scale_percent": "50"}
    r = client.post("/convert-img", files=files, data=data)
    assert r.status_code == 200
    token = r.json()["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    from PIL import Image as PILImage

    im = PILImage.open(io.BytesIO(r2.content))
    assert im.size == (2, 2)


def test_r_unknown_token_404(client):
    r = client.get("/r/" + "0" * 32)
    assert r.status_code == 404


def test_pdf_to_img_zip(client, minimal_pdf_bytes):
    files = {"pdf": ("t.pdf", minimal_pdf_bytes, "application/pdf")}
    data = {"format": "png", "quality": "85", "dpi": "150"}
    r = client.post("/pdf-to-img", files=files, data=data)
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/json"
    j = r.json()
    assert j.get("result_url", "").startswith("/r/")
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r2.content))
    assert any(n.startswith("page_") for n in z.namelist())


def test_pdf_to_img_rejects_non_pdf(client, tiny_png_bytes):
    files = {"pdf": ("x.png", tiny_png_bytes, "image/png")}
    data = {"format": "png", "quality": "85"}
    r = client.post("/pdf-to-img", files=files, data=data)
    assert r.status_code == 400
    assert "error" in r.json()


def test_img_to_pdf(client, tiny_png_bytes):
    files = [("images", ("t.png", tiny_png_bytes, "image/png"))]
    r = client.post("/img-to-pdf", files=files)
    assert r.status_code == 200
    j = r.json()
    assert j.get("result_url", "").startswith("/r/")
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "application/pdf"


def test_img_to_pdf_rejects_bad_extension(client):
    files = [("images", ("x.exe", b"abc", "application/octet-stream"))]
    r = client.post("/img-to-pdf", files=files)
    assert r.status_code == 400
    assert "error" in r.json()


def test_img_to_pdf_no_files_returns_error(client):
    r = client.post("/img-to-pdf")
    assert r.status_code in (400, 422)


def test_merge_pdf(client, minimal_pdf_bytes):
    files = [
        ("pdfs", ("a.pdf", minimal_pdf_bytes, "application/pdf")),
        ("pdfs", ("b.pdf", minimal_pdf_bytes, "application/pdf")),
    ]
    r = client.post("/merge-pdf", files=files)
    assert r.status_code == 200
    j = r.json()
    assert j.get("result_url", "").startswith("/r/")
    token = j["token"]
    r2 = client.get(f"/r/{token}")
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "application/pdf"
    merged = PdfReader(io.BytesIO(r2.content))
    assert len(merged.pages) == 2


def test_merge_pdf_rejects_non_pdf(client, tiny_png_bytes):
    files = [("pdfs", ("x.png", tiny_png_bytes, "image/png"))]
    r = client.post("/merge-pdf", files=files)
    assert r.status_code == 400
    assert "error" in r.json()


def test_merge_pdf_no_files_returns_error(client):
    r = client.post("/merge-pdf")
    assert r.status_code in (400, 422)
