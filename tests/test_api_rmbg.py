"""POST /remove-bg with ML mocked."""

import io
import zipfile
from unittest.mock import patch

from PIL import Image


@patch("app.routers.rmbg.remove_background")
def test_remove_bg_returns_png(mock_rb, client, tiny_png_bytes):
    mock_rb.return_value = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    files = {"image": ("t.png", tiny_png_bytes, "image/png")}
    r = client.post("/remove-bg", files=files)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert len(r.content) > 0
    mock_rb.assert_called_once()


def test_remove_bg_bad_extension(client):
    files = {"image": ("bad.exe", b"xyz", "application/octet-stream")}
    r = client.post("/remove-bg", files=files)
    assert r.status_code == 400
    assert "error" in r.json()


@patch("app.routers.rmbg.remove_background")
def test_remove_bg_bulk_returns_zip(mock_rb, client, tiny_png_bytes):
    mock_rb.return_value = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    files = [
        ("images", ("first.png", tiny_png_bytes, "image/png")),
        ("images", ("second.png", tiny_png_bytes, "image/png")),
    ]
    r = client.post("/remove-bg", files=files)
    assert r.status_code == 200
    data = r.json()
    assert data["media_type"] == "application/zip"
    assert data["file_count"] == 2
    assert data["result_url"].startswith("/r/")

    r2 = client.get(data["result_url"])
    assert r2.status_code == 200
    assert r2.headers.get("content-type") == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(r2.content))
    assert sorted(zf.namelist()) == ["first.png", "second.png"]
    assert all(zf.read(name) for name in zf.namelist())
