"""GET HTML pages."""

import pytest


@pytest.mark.parametrize(
    "path,snippet",
    [
        ("/", "<!DOCTYPE html>"),
        ("/compress-img", "<!DOCTYPE html>"),
        ("/convert-img", "<!DOCTYPE html>"),
        ("/compress-pdf", "<!DOCTYPE html>"),
        ("/pdf-to-img", "<!DOCTYPE html>"),
        ("/img-to-pdf", "<!DOCTYPE html>"),
        ("/merge-pdf", "<!DOCTYPE html>"),
        ("/split-reorder-pdf", "<!DOCTYPE html>"),
    ],
)
def test_pages_return_html(client, path, snippet):
    r = client.get(path)
    assert r.status_code == 200
    assert snippet in r.text


def test_compress_legacy_redirects_to_pdf(client):
    r = client.get("/compress", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers.get("location").rstrip("/").endswith("/compress-pdf")


@pytest.mark.parametrize(
    "path,expected_title_part",
    [
        ("/", "RMBG 2.0"),
        ("/compress-img", "Image Compressor"),
        ("/convert-img", "Image Converter"),
        ("/compress-pdf", "PDF Compressor"),
        ("/pdf-to-img", "PDF to images"),
        ("/img-to-pdf", "Images to PDF"),
        ("/merge-pdf", "Merge PDF"),
        ("/split-reorder-pdf", "Split + Reorder PDF"),
    ],
)
def test_htmx_requests_return_fragment_not_full_document(client, path, expected_title_part):
    """HX-Request returns main+footer+OOB; no full HTML shell."""
    r = client.get(path, headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<!DOCTYPE" not in r.text
    assert "<main" in r.text
    assert "</footer>" in r.text
    assert "hx-swap-oob" in r.text
    assert expected_title_part in r.text
