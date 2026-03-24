"""RMBG-2.0 — lazy load (torch/transformers + weights) on first use."""

import os
import threading

from PIL import Image

_rmbg_lock = threading.Lock()
_model = None
_device = None
_transform_image = None


def ensure_rmbg_loaded() -> None:
    """Import torch/transformers and load weights once; thread-safe."""
    global _model, _device, _transform_image
    if _model is not None:
        return
    with _rmbg_lock:
        if _model is not None:
            return
        import torch
        from torchvision import transforms
        from transformers import AutoModelForImageSegmentation

        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise RuntimeError(
                "HF_TOKEN is not set. RMBG 2.0 is gated — create a token at "
                "https://huggingface.co/settings/tokens and accept the model license at "
                "https://huggingface.co/briaai/RMBG-2.0"
            )

        print("[*] Loading RMBG-2.0 model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = AutoModelForImageSegmentation.from_pretrained(
            "briaai/RMBG-2.0", trust_remote_code=True, token=hf_token
        ).eval().to(device)
        print(f"[OK] Model loaded on {device}")

        image_size = (1024, 1024)
        transform_image = transforms.Compose(
            [
                transforms.Resize(image_size),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

        _model = model
        _device = device
        _transform_image = transform_image


def remove_background(image: Image.Image) -> Image.Image:
    """Run RMBG-2.0 inference and return the image with transparent background."""
    ensure_rmbg_loaded()
    import torch
    from torchvision.transforms import ToPILImage

    original = image.convert("RGB")
    input_tensor = _transform_image(original).unsqueeze(0).to(_device)

    with torch.no_grad():
        preds = _model(input_tensor)[-1].sigmoid().cpu()

    pred = preds[0].squeeze()
    mask = ToPILImage()(pred).resize(original.size)

    result = image.convert("RGBA")
    result.putalpha(mask)
    return result
