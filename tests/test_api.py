import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

API_KEY = "test-api-key"


# ---- /health ----

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ---- /api/parse ----

def test_parse_requires_auth():
    res = client.post("/api/parse")
    assert res.status_code in (401, 403, 422)


def test_parse_rejects_bad_key():
    res = client.post(
        "/api/parse",
        files={"file": ("test.txt", b"hello", "text/plain")},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert res.status_code == 401


def test_parse_rejects_unsupported_type():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.API_KEY = API_KEY
        mock_settings.MAX_FILE_SIZE_MB = 10
        mock_settings.MAX_PDF_PAGES = 10

        res = client.post(
            "/api/parse",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert res.status_code == 415


def test_parse_rejects_large_file():
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.API_KEY = API_KEY
        mock_settings.MAX_FILE_SIZE_MB = 10
        mock_settings.MAX_PDF_PAGES = 10

        big_file = b"x" * (11 * 1024 * 1024)  # 11MB
        res = client.post(
            "/api/parse",
            files={"file": ("big.jpg", big_file, "image/jpeg")},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert res.status_code == 413


# ---- RapidAPI proxy auth tests ----

def test_parse_accepts_rapidapi_proxy_secret():
    with patch("app.services.auth_middleware.settings") as mock_settings:
        mock_settings.API_KEY = API_KEY
        mock_settings.RAPIDAPI_PROXY_SECRET = "test-rapidapi-secret"

        res = client.post(
            "/api/parse",
            files={"file": ("test.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")},
            headers={"X-RapidAPI-Proxy-Secret": "test-rapidapi-secret"},
        )
        assert res.status_code != 401


def test_parse_rejects_wrong_rapidapi_secret():
    with patch("app.services.auth_middleware.settings") as mock_settings:
        mock_settings.API_KEY = API_KEY
        mock_settings.RAPIDAPI_PROXY_SECRET = "test-rapidapi-secret"

        res = client.post(
            "/api/parse",
            files={"file": ("test.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")},
            headers={"X-RapidAPI-Proxy-Secret": "wrong-secret"},
        )
        assert res.status_code == 401


# ---- parser_service unit tests ----

def test_extract_json_strips_fences():
    from app.services.parser_service import _extract_json
    raw = "```json\n{\"total\": 12.50}\n```"
    result = _extract_json(raw)
    assert result["total"] == 12.50


def test_merge_single_page_passthrough():
    import asyncio
    from app.services.parser_service import merge_pages
    page = {"merchant": {"name": "Test Store"}, "total": 9.99}
    with patch("app.services.parser_service.client"):
        result = asyncio.run(merge_pages([page]))
    assert result == page  # Single page — no merge call needed


# ---- pdf_service unit tests ----

def test_pdf_page_limit():
    from app.services.pdf_service import pdf_to_images, PDFConversionError
    fake_pages = [MagicMock()] * 15  # 15 pages > MAX_PDF_PAGES (10)
    with patch("app.services.pdf_service.convert_from_bytes", return_value=fake_pages):
        with pytest.raises(PDFConversionError, match="Maximum allowed"):
            pdf_to_images(b"fake-pdf-bytes")
