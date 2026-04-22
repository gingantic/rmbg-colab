"""Image upscaling using local Real-ESRGAN models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import threading
import urllib.request
from urllib.error import URLError

import numpy as np
from PIL import Image

from app.config import get_settings
from app.utils.image_safe import ensure_image_within_limits
from app.utils.quality import normalize_upscale_factor

UPSCALE_MODES = frozenset({"general", "animation"})

_MODEL_META = {
    "general": {
        "filename": "realesr-general-x4v3.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "model_kind": "srvgg_general_x4",
        "native_scale": 4,
    },
    "animation": {
        "filename": "realesr-animevideov3.pth",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
        "model_kind": "srvgg_anime_x4",
        "native_scale": 4,
    },
}

_ENGINE_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()
_ENGINES: dict[str, "_UpscaleEngine"] = {}


@dataclass
class _UpscaleEngine:
    model_name: str
    native_scale: int
    runner: object


def _normalize_mode(raw: str | None) -> str:
    mode = (raw or "").strip().lower()
    return mode if mode in UPSCALE_MODES else "general"


def _require_runtime():
    try:
        # Compatibility shim: older basicsr imports torchvision.transforms.functional_tensor,
        # while newer torchvision exposes this as torchvision.transforms._functional_tensor.
        import torchvision.transforms._functional_tensor as _tv_functional_tensor
        sys.modules.setdefault(
            "torchvision.transforms.functional_tensor",
            _tv_functional_tensor,
        )

        import cv2
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        from realesrgan.archs.srvgg_arch import SRVGGNetCompact
    except Exception as exc:  # pragma: no cover - runtime-only dependency check
        raise ValueError(
            "Upscaler runtime is not available. Install dependencies for Real-ESRGAN."
        ) from exc
    return cv2, RRDBNet, RealESRGANer, SRVGGNetCompact


def _download_model_if_missing(mode: str) -> Path:
    meta = _MODEL_META[mode]
    settings = get_settings()
    models_dir = Path(settings.upscaler_models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / meta["filename"]
    if path.exists():
        return path
    try:
        urllib.request.urlretrieve(meta["url"], path)
    except URLError as exc:
        raise ValueError(
            f"Failed to download upscaler model '{meta['filename']}'. Check internet connection and try again."
        ) from exc
    return path


def _build_runner(mode: str) -> _UpscaleEngine:
    cv2, RRDBNet, RealESRGANer, SRVGGNetCompact = _require_runtime()
    _ = cv2
    meta = _MODEL_META[mode]
    model_path = _download_model_if_missing(mode)
    if meta["model_kind"] == "rrdb_x4plus":
        model = RRDBNet(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_block=23,
            num_grow_ch=32,
            scale=4,
        )
    elif meta["model_kind"] == "srvgg_general_x4":
        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_conv=32,
            upscale=4,
            act_type="prelu",
        )
    else:
        model = SRVGGNetCompact(
            num_in_ch=3,
            num_out_ch=3,
            num_feat=64,
            num_conv=16,
            upscale=4,
            act_type="prelu",
        )

    runner = RealESRGANer(
        scale=meta["native_scale"],
        model_path=str(model_path),
        model=model,
        # Use tiling to reduce memory spikes on large images.
        tile=256,
        tile_pad=10,
        pre_pad=0,
        half=False,
    )
    return _UpscaleEngine(model_name=meta["filename"], native_scale=meta["native_scale"], runner=runner)


def _get_engine(mode: str) -> _UpscaleEngine:
    normalized_mode = _normalize_mode(mode)
    with _ENGINE_LOCK:
        existing = _ENGINES.get(normalized_mode)
        if existing is not None:
            return existing
        try:
            created = _build_runner(normalized_mode)
        except RuntimeError:
            # Recover once from corrupted/incomplete checkpoint downloads.
            model_path = Path(get_settings().upscaler_models_dir) / _MODEL_META[normalized_mode]["filename"]
            if model_path.exists():
                model_path.unlink(missing_ok=True)
            created = _build_runner(normalized_mode)
        _ENGINES[normalized_mode] = created
        return created


def preload_upscaler_models() -> None:
    """Warm up both upscaler models in memory."""
    for mode in UPSCALE_MODES:
        _get_engine(mode)


def upscale_to_buffer(image: Image.Image, mode: str, scale: int) -> tuple:
    """Upscale image with selected mode and scale; return (buffer, mimetype, ext)."""
    cv2, _, _, _ = _require_runtime()
    normalized_mode = _normalize_mode(mode)
    outscale = normalize_upscale_factor(scale)
    settings = get_settings()
    max_edge = settings.upscaler_max_output_edge_px

    src_w, src_h = image.size
    target_w = src_w * outscale
    target_h = src_h * outscale
    if max(target_w, target_h) > max_edge:
        raise ValueError(
            f"Requested output is too large ({target_w}x{target_h}). "
            f"Reduce scale or use a smaller input (max edge {max_edge}px)."
        )

    engine = _get_engine(normalized_mode)

    rgb = image.convert("RGB")
    arr = np.array(rgb, dtype=np.uint8)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    # RealESRGANer is not reliably thread-safe under concurrent requests.
    with _INFER_LOCK:
        output_bgr, _ = engine.runner.enhance(bgr, outscale=float(outscale))
    output_rgb = cv2.cvtColor(output_bgr, cv2.COLOR_BGR2RGB)
    output_image = Image.fromarray(output_rgb)

    if max(output_image.size) > max_edge:
        raise ValueError(
            f"Upscaled image is too large. Reduce scale or use a smaller input (max edge {max_edge}px)."
        )
    ensure_image_within_limits(output_image)

    from io import BytesIO

    buf = BytesIO()
    output_image.save(buf, format="PNG", optimize=True)
    return buf, "image/png", "png"
