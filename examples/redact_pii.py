import base64
import io
import json
import sys
from pathlib import Path

import anthropic
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.compress_images import compress_image_for_claude

IMAGES = [
    "Carulla-grocery.jpg",
    "gym-invoice.jpg",
    "wholeFoodsReceipt.JPG",
]

PII_PROMPT = """Identify all personal information in this receipt image that should be redacted:
names, phone numbers, credit/debit card numbers or last-4 digits, national IDs, account numbers, email addresses.

Return ONLY a JSON object — no markdown, no explanation:
{
  "pii_regions": [
    {"label": "name", "x": 0.05, "y": 0.12, "w": 0.30, "h": 0.04}
  ]
}
x, y = top-left corner as fraction of image width/height (0.0–1.0)
w, h = width/height as fraction of image dimensions
Add generous padding around each region to fully cover the text."""


def blur_region(img: Image.Image, x: float, y: float, w: float, h: float) -> Image.Image:
    iw, ih = img.size
    left   = max(0, int(x * iw))
    top    = max(0, int(y * ih))
    right  = min(iw, int((x + w) * iw))
    bottom = min(ih, int((y + h) * ih))
    region = img.crop((left, top, right, bottom))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=20))
    img.paste(blurred, (left, top))
    return img


def detect_pii(client: anthropic.Anthropic, image_bytes: bytes) -> list[dict]:
    compressed, media_type = compress_image_for_claude(image_bytes)
    b64 = base64.standard_b64encode(compressed).decode()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": PII_PROMPT},
            ],
        }],
    )
    raw = msg.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw).get("pii_regions", [])


def redact(image_path: Path, client: anthropic.Anthropic) -> None:
    data = image_path.read_bytes()

    regions = detect_pii(client, data)
    if not regions:
        print(f"  No PII detected in {image_path.name}")
        return

    img = Image.open(io.BytesIO(data)).convert("RGB")
    for r in regions:
        print(f"  Blurring: {r['label']}")
        img = blur_region(img, r["x"], r["y"], r["w"], r["h"])

    img.save(image_path, format="JPEG", quality=92)
    print(f"  Saved: {image_path.name}")


if __name__ == "__main__":
    client = anthropic.Anthropic()
    base = Path(__file__).parent
    for name in IMAGES:
        print(f"\nProcessing {name}...")
        redact(base / name, client)
