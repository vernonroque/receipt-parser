# 🧾 Receipt Parser API

> Extract structured data from receipts instantly — line items, totals, taxes, merchant info, payment methods, and dates from JPEG, PNG, WebP, or PDF files.

---

## Table of Contents

- [Overview](#overview)
- [Getting Started on RapidAPI](#getting-started-on-rapidapi)
- [Authentication](#authentication)
- [Endpoint](#endpoint)
- [Response Schema](#response-schema)
- [Code Examples](#code-examples)
  - [Python](#python)
  - [cURL](#curl)
  - [Node.js](#nodejs)
- [Error Codes](#error-codes)
- [Rate Limits & Pricing](#rate-limits--pricing)
- [FAQ](#faq)
- [Support](#support)

---

<a id="overview"></a>

## Overview

The **Receipt Parser API** turns any receipt image or PDF into clean, structured JSON in milliseconds. Whether you're building an expense tracker, accounting integration, or reimbursement workflow — this API handles the heavy lifting.

**Supported input formats:**

| Format | MIME Type |
|---|---|
| JPEG | `image/jpeg` |
| PNG | `image/png` |
| WebP | `image/webp` |
| PDF | `application/pdf` |

**What it extracts:**

| Field | Description |
|---|---|
| `merchant` | Store name, address, and phone number |
| `date` | Transaction date and time |
| `line_items` | Individual products with name, quantity, and price |
| `subtotal` | Pre-tax total |
| `tax` | Tax amount and rate |
| `total` | Final charged amount |
| `payment_method` | Card type and last 4 digits (or cash) |
| `currency` | Detected currency code (e.g. `USD`, `EUR`) |

---

<a id="getting-started-on-rapidapi"></a>

## Getting Started on RapidAPI

1. **Subscribe** to the Receipt Parser API on [RapidAPI](https://rapidapi.com)
2. Copy your `X-RapidAPI-Key` from the RapidAPI dashboard
3. Copy your `X-RapidAPI-Host` shown on the API listing page
4. Make your first request using the examples below — you'll have structured data in under a minute

---

<a id="authentication"></a>

## Authentication

Every request requires these two headers:

```
X-RapidAPI-Key: YOUR_RAPIDAPI_KEY
X-RapidAPI-Host: receipt-parser2.p.rapidapi.com
```

> ⚠️ Never hardcode your API key. Use environment variables to keep it secure.

```python
import os
API_KEY = os.environ.get("RAPIDAPI_KEY")
```

---

<a id="endpoint"></a>

## Endpoint

Base URL: `https://receipt-parser2.p.rapidapi.com`

### Parse Receipt

Upload any supported file — JPEG, PNG, WebP, or PDF — and receive structured receipt data in return. This single endpoint handles all file types automatically.

```
POST /api/parse
```

**Headers:**

| Header | Value |
|---|---|
| `X-RapidAPI-Key` | Your RapidAPI key |
| `X-RapidAPI-Host` | `receipt-parser2.p.rapidapi.com` |
| `Content-Type` | `multipart/form-data` |

**Body (form-data):**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✅ | Receipt file — JPEG, PNG, WebP, or PDF (max 10MB) |
| `language` | String | ❌ | Language hint, e.g. `en`, `es`, `fr` (default: `en`) |

> **Note:** Handles multi-page PDFs of receipts or invoices

---

<a id="response-schema"></a>

## Response Schema

The endpoint returns the following JSON structure.

**Success Response (`200 OK`):**

```json
{
  "success": true,
  "pages_processed": 1,
  "data": {
    "merchant": {
      "name": "carulla fresh market calle 63",
      "address": null,
      "phone": null,
      "website": null,
      "tax_id": "8909006089"
    },
    "date": "2026-04-12",
    "invoice_number": "UH189633",
    "line_items": [
      {
        "description": "Cafe Gourmet Tos",
        "quantity": 1,
        "unit_price": 45.3,
        "total": 45.3
      },
      {
        "description": "Manzana Bolsa In",
        "quantity": 1,
        "unit_price": 12.38,
        "total": 12.38
      },
      {
        "description": "Agua Sin gas",
        "quantity": 1,
        "unit_price": 3.8,
        "total": 3.8
      }
    ],
    "subtotal": 61.48,
    "tax": null,
    "tip": null,
    "discount": 0,
    "total": 61.48,
    "currency": "COP",
    "payment_method": "TARJETA DEBITO",
    "notes": "COMPRA POR WHATSAPP305261446"
  },
  "error": null
}
```

**Field Reference:**

| Field | Type | Description |
|---|---|---|
| `success` | Boolean | `true` on success, `false` on failure |
| `pages_processed` | Number | Number of pages parsed from the uploaded file |
| `error` | String \| null | Error message if `success` is `false`, otherwise `null` |
| `data.merchant.name` | String \| null | Store or restaurant name |
| `data.merchant.address` | String \| null | Address if visible on receipt |
| `data.merchant.phone` | String \| null | Phone number if visible |
| `data.merchant.website` | String \| null | Website if visible |
| `data.merchant.tax_id` | String \| null | Merchant tax or business ID if visible |
| `data.date` | String \| null | Transaction date in `YYYY-MM-DD` format |
| `data.invoice_number` | String \| null | Invoice or receipt number if present |
| `data.line_items` | Array | List of purchased items (empty array if none detected) |
| `data.line_items[].description` | String | Item name |
| `data.line_items[].quantity` | Number | Quantity purchased |
| `data.line_items[].unit_price` | Number | Price per unit |
| `data.line_items[].total` | Number | Line total |
| `data.subtotal` | Number \| null | Pre-tax, pre-tip total |
| `data.tax` | Number \| null | Tax amount if visible |
| `data.tip` | Number \| null | Tip amount if visible |
| `data.discount` | Number \| null | Discount amount applied |
| `data.total` | Number \| null | Final total charged |
| `data.currency` | String \| null | ISO 4217 currency code (e.g. `USD`, `COP`, `EUR`) |
| `data.payment_method` | String \| null | Payment method as printed on receipt (e.g. `TARJETA DEBITO`, `CASH`) |
| `data.notes` | String \| null | Any additional notes or text detected on the receipt |

> **Note:** Fields that cannot be detected on the receipt are returned as `null`.

---

<a id="code-examples"></a>

## Code Examples

### Python

Install `requests` if you haven't already:

```bash
pip install requests
```

**Parse a JPEG / PNG / WebP image:**

```python
import requests
import os

API_KEY = os.environ.get("RAPIDAPI_KEY")

url = "https://receipt-parser2.p.rapidapi.com/api/parse"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com",
}

with open("receipt.jpg", "rb") as f:
    files = {"file": ("receipt.jpg", f, "image/jpeg")}
    response = requests.post(url, files=files, headers=headers)

data = response.json()

if data["success"]:
    receipt = data["data"]
    print(f"Merchant:  {receipt['merchant']['name']}")
    print(f"Date:      {receipt['date']}")
    print(f"Invoice:   {receipt['invoice_number']}")
    print(f"Total:     {receipt['currency']} {receipt['total']}")
    print(f"Paid with: {receipt['payment_method']}")
    print("\nLine Items:")
    for item in receipt["line_items"]:
        print(f"  - {item['description']} x{item['quantity']}  {item['total']}")
else:
    print("Error:", data["error"])
```

**Parse a WebP image:**

```python
import requests
import os

API_KEY = os.environ.get("RAPIDAPI_KEY")

url = "https://receipt-parser2.p.rapidapi.com/api/parse"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com",
}

with open("receipt.webp", "rb") as f:
    files = {"file": ("receipt.webp", f, "image/webp")}
    response = requests.post(url, files=files, headers=headers)

print(response.json())
```

**Parse a PDF:**

```python
import requests
import os

API_KEY = os.environ.get("RAPIDAPI_KEY")

url = "https://receipt-parser2.p.rapidapi.com/api/parse"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com",
}

with open("receipt.pdf", "rb") as f:
    files = {"file": ("receipt.pdf", f, "application/pdf")}
    response = requests.post(url, files=files, headers=headers)

print(response.json())
```

**Batch process a folder of receipts:**

```python
import requests
import os
from pathlib import Path

API_KEY = os.environ.get("RAPIDAPI_KEY")
RECEIPTS_DIR = "./receipts"

MIME_TYPES = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
    ".pdf":  "application/pdf",
}

def parse_receipt(filepath: Path) -> dict:
    ext = filepath.suffix.lower()
    mime = MIME_TYPES.get(ext)
    if not mime:
        return {"success": False, "error": {"message": f"Unsupported file type: {ext}"}}

    endpoint = "api/parse"
    url = f"https://receipt-parser2.p.rapidapi.com/{endpoint}"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com",
    }

    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, mime)}
        response = requests.post(url, files=files, headers=headers)

    return response.json()


for receipt_file in Path(RECEIPTS_DIR).iterdir():
    result = parse_receipt(receipt_file)
    if result.get("success"):
        total = result["data"]["total"]
        merchant = result["data"]["merchant"]["name"]
        currency = result["data"]["currency"]
        print(f"✅ {receipt_file.name}: {merchant} — {currency} {total}")
    else:
        print(f"❌ {receipt_file.name}: {result.get('error', 'Unknown error')}")
```

---

### cURL

**Image upload (JPEG / PNG / WebP):**

```bash
curl -X POST "https://receipt-parser2.p.rapidapi.com/api/parse" \
  -H "X-RapidAPI-Key: YOUR_RAPIDAPI_KEY" \
  -H "X-RapidAPI-Host: receipt-parser2.p.rapidapi.com" \
  -F "file=@/path/to/receipt.jpg"
```

**PDF upload:**

```bash
curl -X POST "https://receipt-parser2.p.rapidapi.com/api/parse" \
  -H "X-RapidAPI-Key: YOUR_RAPIDAPI_KEY" \
  -H "X-RapidAPI-Host: receipt-parser2.p.rapidapi.com" \
  -F "file=@/path/to/receipt.pdf"
```

---

### Node.js

```javascript
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");

const form = new FormData();
form.append("file", fs.createReadStream("./receipt.jpg"));

const response = await axios.post(
  "https://receipt-parser2.p.rapidapi.com/api/parse",
  form,
  {
    headers: {
      ...form.getHeaders(),
      "X-RapidAPI-Key": process.env.RAPIDAPI_KEY,
      "X-RapidAPI-Host": "receipt-parser2.p.rapidapi.com",
    },
  }
);

console.log(response.data);
```

---

<a id="error-codes"></a>

## Error Codes

| HTTP Status | Code | Description |
|---|---|---|
| `400` | `INVALID_INPUT` | Missing or malformed request body |
| `400` | `UNSUPPORTED_FORMAT` | File type not supported — use JPEG, PNG, WebP, or PDF |
| `400` | `FILE_TOO_LARGE` | File exceeds the 10MB size limit |
| `401` | `UNAUTHORIZED` | Missing or invalid API key |
| `422` | `PARSE_FAILED` | Receipt could not be parsed — likely low image quality |
| `429` | `RATE_LIMIT_EXCEEDED` | Too many requests — slow down or upgrade your plan |
| `500` | `INTERNAL_ERROR` | Unexpected server error — retry after a moment |

**Error Response Shape:**

```json
{
  "success": false,
  "pages_processed": 0,
  "data": null,
  "error": "Unable to extract data from the provided file. Ensure the receipt is well-lit, in focus, and fully visible."
}
```

---

<a id="rate-limits--pricing"></a>

## Rate Limits & Pricing

| Plan | Requests / Month |
|---|---|
| Basic | 5 |
| Pro | 100 |
| Ultra | 300 |

View full pricing on the [RapidAPI listing page](https://rapidapi.com).

---

<a id="faq"></a>

## FAQ

**Q: What image quality works best?**  
A: Good lighting, minimal blur, and the full receipt in frame will yield the highest confidence scores. Avoid heavy shadows and extreme angles.

**Q: My WebP image returned a low confidence score — why?**  
A: WebP files compressed heavily or exported from screenshots may lose fine detail. Try uploading the original JPEG or PNG source if available.

**Q: Can it handle multi-page PDFs?**  
A: Only the first page of a PDF is currently processed. Ensure the receipt content is on page 1.

**Q: Are non-English receipts supported?**  
A: Yes. Pass a `language` hint (e.g. `"es"` for Spanish, `"fr"` for French) for best results. Auto-detection is enabled by default.

**Q: Is my receipt data stored?**  
A: No receipt data is retained after processing. See the privacy policy on the RapidAPI listing for full details.

---

<a id="support"></a>

## Support

- 💬 Use the **RapidAPI discussion board** on the listing page for public questions
- 🐛 Found a bug? Contact support via RapidAPI messaging
- ⭐ If this API saves you time, please leave a rating on RapidAPI — it helps a lot!

---

*Built with Python 🐍 · Hosted on [RapidAPI](https://rapidapi.com)*
