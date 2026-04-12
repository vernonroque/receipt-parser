# Receipt / Invoice Parser API

Upload an image or PDF receipt/invoice → get structured JSON back with merchant info, line items, and totals.

Built with **FastAPI**, **Claude Vision API**, and **Supabase Auth**.

---

## Features

- 📄 Parses JPEG, PNG, WEBP images and multi-page PDFs
- 🧠 Claude vision model extracts merchant, line items, totals, tax, tip, currency
- 🔐 Supabase Auth (Google OAuth + magic link) + API key management
- 🚀 Deploy-ready for Railway (poppler included via nixpacks)

---

## Project Structure

```
receipt-parser/
├── app/
│   ├── main.py                  # FastAPI app + middleware setup
│   ├── api/
│   │   ├── parse.py             # POST /api/parse — main upload endpoint
│   │   ├── auth.py              # POST /auth/verify — token verification
│   │   └── keys.py              # GET/POST/DELETE /keys — API key management
│   ├── core/
│   │   ├── config.py            # Environment variable settings
│   │   └── supabase.py          # Supabase client singleton
│   ├── models/
│   │   └── schemas.py           # Pydantic models (ParsedReceipt, APIKey, etc.)
│   └── services/
│       ├── auth_middleware.py   # JWT + API key validation
│       ├── parser_service.py    # Claude vision extraction + JSON merging
│       └── pdf_service.py       # PDF → image conversion via pdf2image
├── tests/
│   └── test_api.py              # Pytest test suite
├── scripts/
│   └── supabase_migration.sql   # Run this in Supabase SQL Editor
├── .env.example                 # Copy to .env and fill in values
├── requirements.txt
├── railway.toml                 # Railway deployment config
└── nixpacks.toml                # Installs poppler on Railway
```

---

## Quickstart

### 1. Clone and install dependencies

```bash
git clone <your-repo>
cd receipt-parser

# Install poppler (required for PDF support)
# macOS:
brew install poppler
# Ubuntu/Debian:
sudo apt-get install -y poppler-utils
# Windows: download from https://github.com/oschwartz10612/poppler-windows

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to **Authentication → Providers** and enable **Google OAuth**
   - You'll need a Google OAuth client ID/secret from [console.cloud.google.com](https://console.cloud.google.com)
3. Go to **SQL Editor** and run the contents of `scripts/supabase_migration.sql`
4. Go to **Project Settings → API** and copy:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` ⚠️ Keep this secret

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Anthropic API key and Supabase credentials
```

### 4. Run locally

```bash
uvicorn app.main:app --reload
```

API is now running at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## API Reference

### Authentication

All endpoints (except `/health`) require one of:

| Method | Header format |
|---|---|
| Supabase JWT | `Authorization: Bearer <supabase_jwt>` |
| API Key | `Authorization: Bearer rp_live_<key>` |

---

### `POST /api/parse`

Upload a receipt or invoice image/PDF. Returns structured JSON.

**Request:**
```
Content-Type: multipart/form-data
Authorization: Bearer <token>

file: <image or PDF file>
```

**Supported file types:** `image/jpeg`, `image/png`, `image/webp`, `application/pdf`
**Max file size:** 10MB
**Max PDF pages:** 10

**Response:**
```json
{
  "success": true,
  "pages_processed": 1,
  "data": {
    "merchant": {
      "name": "Whole Foods Market",
      "address": "1234 Main St, Austin TX 78701",
      "phone": "512-555-0100",
      "website": null,
      "tax_id": null
    },
    "date": "2024-11-15",
    "invoice_number": null,
    "line_items": [
      { "description": "Organic Bananas", "quantity": 1.2, "unit_price": 0.69, "total": 0.83 },
      { "description": "Almond Milk 64oz", "quantity": 2, "unit_price": 4.99, "total": 9.98 }
    ],
    "subtotal": 10.81,
    "tax": 0.89,
    "tip": null,
    "discount": null,
    "total": 11.70,
    "currency": "USD",
    "payment_method": "Visa ending 4242",
    "notes": null
  }
}
```

---

### `POST /keys`

Create a new API key. The full key is returned **once only** — store it securely.

**Request:**
```json
{ "name": "Production" }
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Production",
  "key": "rp_live_aBcDeFgH...",
  "created_at": "2024-11-15T10:00:00Z"
}
```

---

### `GET /keys`

List all active API keys (previews only — full key never returned again).

---

### `DELETE /keys/{key_id}`

Revoke an API key. Cannot be undone.

---

### `POST /auth/verify`

Verify a Supabase JWT and return user info. Call this from your frontend after OAuth login.

**Request:**
```json
{ "access_token": "<supabase_jwt>" }
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deploying to Railway

1. Push your code to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Add environment variables in Railway dashboard (same as your `.env`)
4. Railway will automatically use `nixpacks.toml` to install poppler
5. Your API will be live at `https://your-app.up.railway.app`

> **Tip:** Railway's free tier is enough for early testing. Upgrade when you need always-on uptime.

---

## Rate Limiting (Add Later)

For the MVP, rate limiting is handled at the API key level via `request_count` in the database.
When you're ready to enforce limits, add [slowapi](https://github.com/laurentS/slowapi) — it drops in as FastAPI middleware in ~20 lines.

---

## Adding PDF Support on Render

If you deploy to Render instead of Railway, add this to your `render.yaml`:

```yaml
buildCommand: "apt-get install -y poppler-utils && pip install -r requirements.txt"
```

---

## License

MIT
