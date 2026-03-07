import os
import io
import sys
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB max upload

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'}

# ---------------------------------------------------------------------------
# Model Loading
# ---------------------------------------------------------------------------
HF_TOKEN = os.environ.get('HF_TOKEN')

if not HF_TOKEN:
    print("=" * 60)
    print("  ERROR: HF_TOKEN environment variable not set.")
    print()
    print("  RMBG 2.0 is a gated model. You need to:")
    print("  1. Create an account at https://huggingface.co")
    print("  2. Accept the model license at:")
    print("     https://huggingface.co/briaai/RMBG-2.0")
    print("  3. Create an access token at:")
    print("     https://huggingface.co/settings/tokens")
    print("  4. Set the token before running:")
    print('     set HF_TOKEN=hf_your_token_here   (Windows)')
    print('     export HF_TOKEN=hf_your_token_here (Linux/Mac)')
    print("=" * 60)
    sys.exit(1)

print("[*] Loading RMBG-2.0 model...")
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = AutoModelForImageSegmentation.from_pretrained(
    'briaai/RMBG-2.0', trust_remote_code=True, token=HF_TOKEN
).eval().to(device)
print(f"[OK] Model loaded on {device}")

IMAGE_SIZE = (1024, 1024)
transform_image = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def remove_background(image: Image.Image) -> Image.Image:
    """Run RMBG-2.0 inference and return the image with transparent background."""
    original = image.convert('RGB')
    input_tensor = transform_image(original).unsqueeze(0).to(device)

    with torch.no_grad():
        preds = model(input_tensor)[-1].sigmoid().cpu()

    pred = preds[0].squeeze()
    mask = transforms.ToPILImage()(pred).resize(original.size)

    result = image.convert('RGBA')
    result.putalpha(mask)
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/remove-bg', methods=['POST'])
def remove_bg():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided.'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    try:
        image = Image.open(file.stream)
        result = remove_background(image)

        buf = io.BytesIO()
        result.save(buf, format='PNG')
        buf.seek(0)

        return send_file(
            buf,
            mimetype='image/png',
            as_attachment=False,
            download_name=f'rmbg_{uuid.uuid4().hex[:8]}.png',
        )
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
