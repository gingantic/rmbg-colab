"""POST /remove-bg with ML mocked."""

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
