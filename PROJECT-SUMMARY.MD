# Receipt Parser — Project Summary

## What It Does

A FastAPI REST API that accepts receipt/invoice images (or PDFs) and returns structured JSON data extracted by Claude Vision. No database, no user accounts — just file-in → structured-JSON-out.

---

## End-to-End Request Flow

```
Client uploads image/PDF (multipart/form-data)
       ↓
Bearer token auth check
       ↓
File validation (type: JPEG/PNG/WEBP/PDF, size: <10MB)
       ↓
PDF? → convert each page to JPEG (pdf2image + poppler, max 10 pages)
       ↓
Compress each image to fit Claude's 5MB base64 limit (Pillow)
       ↓
Per-page: encode to base64 → call Claude Vision API → parse extracted JSON
       ↓
Multi-page? → second Claude call to merge all page results
       ↓
Pydantic validation → fill missing fields with null
       ↓
Return ParseResponse JSON (success, pages_processed, ParsedReceipt data)
```

---

## Key Files

| File | Role |
|------|------|
| `app/main.py` | FastAPI app init, CORS middleware, `/health` route |
| `app/api/parse.py` | `POST /api/parse` — orchestrates the full parse flow |
| `app/services/parser_service.py` | Core Claude API calls (extraction + merge prompts) |
| `app/services/pdf_service.py` | PDF → JPEG conversion via `pdf2image` |
| `app/services/compress_images.py` | Image compression via Pillow (quality reduction + downscaling) |
| `app/services/auth_middleware.py` | Bearer token + RapidAPI proxy secret validation |
| `app/models/schemas.py` | Pydantic models: `Merchant`, `LineItem`, `ParsedReceipt`, `ParseResponse` |
| `app/core/config.py` | Pydantic settings — loads all env vars |
| `tests/test_api.py` | Pytest suite (unit + integration) |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Web framework | FastAPI 0.115.0 + Uvicorn 0.30.6 |
| AI / Vision | Anthropic SDK 0.34.2 — `claude-sonnet-4-20250514` |
| PDF processing | pdf2image 1.17.0 + poppler (system dep) |
| Image processing | Pillow 10.4.0 |
| Data validation | Pydantic 2.9.2 |
| Testing | Pytest 8.3.3 + pytest-asyncio 0.24.0 |
| Runtime | Python 3.12 |
| Deployment | Docker + Railway |

---

## The Two Claude API Calls

1. **Extraction** (per page, max 1500 tokens)
   - Sends: base64-encoded image + extraction prompt defining expected JSON structure
   - Returns: merchant info, line items, totals, tax, tip, currency, date
   - Fallback: if Claude returns malformed JSON, a second call asks Claude to repair it

2. **Merge** (multi-page receipts only, max 2000 tokens)
   - Sends: all per-page extracted JSON results
   - Returns: single merged receipt (last page's totals, first non-null values for merchant/date, combined line items)
   - Fallback: returns the most complete single-page result if merge fails

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | ✅ | — | Claude API authentication |
| `API_KEY` | ✅ | — | Static Bearer token for client auth |
| `RAPIDAPI_PROXY_SECRET` | ❌ | `""` | Alternative auth for RapidAPI proxy |
| `ALLOWED_ORIGINS` | ❌ | `["http://localhost:3000"]` | CORS allowed origins |
| `MAX_FILE_SIZE_MB` | ❌ | `10` | Max upload size in MB |
| `MAX_PDF_PAGES` | ❌ | `10` | Max pages per PDF |

See `.env.example` for the full template.

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/api/parse` | Bearer token | Upload receipt/invoice, get structured JSON |

---

## Deployment

- **Dockerfile** — Python 3.12 slim, installs `poppler-utils`, runs `uvicorn` on `0.0.0.0:8000`
- **railway.toml** — Dockerfile builder, health check at `/health`, auto-restart on failure
