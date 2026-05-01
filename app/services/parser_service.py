import anthropic
import asyncio
import base64
import json
import re
from typing import List
from app.core.config import settings
from app.models.schemas import ParsedReceipt

client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = """
You are a receipt and invoice data extraction engine.

Carefully analyze this image and extract ALL available information.
Return ONLY a single valid JSON object — no markdown, no explanation, no backticks.

Use exactly this structure (use null for any field you cannot find):
{
  "merchant": {
    "name": null,
    "address": null,
    "phone": null,
    "website": null,
    "tax_id": null
  },
  "date": null,
  "invoice_number": null,
  "line_items": [
    {
      "description": null,
      "quantity": null,
      "unit_price": null,
      "total": null
    }
  ],
  "subtotal": null,
  "tax": null,
  "tip": null,
  "discount": null,
  "total": null,
  "currency": null,
  "payment_method": null,
  "notes": null
}

Rules:
- All monetary values must be numbers (floats), not strings. E.g. 12.50 not "$12.50"
- Date must be ISO 8601 format: YYYY-MM-DD
- Currency must be ISO 4217 format: USD, EUR, GBP, COP, etc.
- If this is a multi-page document, extract only what is visible on THIS page
"""

MERGE_PROMPT = """
You are merging extracted data from multiple pages of the same invoice or receipt.
Each page's data is provided below as JSON.

Return ONLY a single merged JSON object — no markdown, no explanation, no backticks.

Rules:
- Combine ALL line_items from all pages into one list (deduplicate if clearly the same item)
- Use the merchant info from whichever page has the most complete data
- The "total" should come from the LAST page (summary page)
- "subtotal", "tax", "tip", "discount" should come from the page where they appear most completely
- For "date" and "invoice_number", use the first non-null value found
- Prefer non-null values over null values for all fields

Pages data:
{pages_json}

Return the merged result using the same JSON structure as the input pages.
"""


def _image_to_b64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def _extract_json(text: str) -> dict:
    """Robustly extract JSON from Claude's response, handling edge cases."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def parse_single_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Send one image to Claude and return the raw parsed dict."""
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=700,
        system=[
            {
                "type": "text",
                "text": EXTRACTION_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": _image_to_b64(image_bytes),
                        },
                    }
                ],
            }
        ],
    )

    raw_text = response.content[0].text
    try:
        return _extract_json(raw_text)
    except json.JSONDecodeError:
        # Ask Claude to fix its own output
        return await _repair_json(raw_text)


async def _repair_json(bad_output: str) -> dict:
    """Ask Claude to repair malformed JSON output."""
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=900,
        messages=[
            {
                "role": "user",
                "content": f"""The following text should be valid JSON but is malformed.
Fix it and return ONLY the corrected JSON object, no explanation, no backticks:

{bad_output}""",
            }
        ],
    )
    return json.loads(response.content[0].text.strip())


async def merge_pages(pages_data: List[dict]) -> dict:
    """Merge multiple page extractions into one coherent result using Claude."""
    if len(pages_data) == 1:
        return pages_data[0]

    response = await client.messages.create(
        model=_MODEL,
        max_tokens=900,
        messages=[
            {
                "role": "user",
                "content": MERGE_PROMPT.format(
                    pages_json=json.dumps(pages_data, indent=2)
                ),
            }
        ],
    )

    raw_text = response.content[0].text
    try:
        return _extract_json(raw_text)
    except json.JSONDecodeError:
        # Fallback: return the page with the most complete data
        return max(pages_data, key=lambda p: sum(1 for v in p.values() if v is not None))


async def parse_images(image_bytes_list: List[bytes]) -> tuple[ParsedReceipt, int]:
    """
    Parse one or more page images and return a merged ParsedReceipt.
    Returns (parsed_receipt, pages_processed).
    """
    pages_data = list(await asyncio.gather(
        *[parse_single_image(img, media_type="image/jpeg") for img in image_bytes_list]
    ))

    merged = await merge_pages(pages_data)

    # Validate through Pydantic (fills in missing fields with None)
    parsed = ParsedReceipt(**merged)
    return parsed, len(pages_data)
