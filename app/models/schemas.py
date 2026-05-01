from pydantic import BaseModel
from typing import List, Optional


class Merchant(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    tax_id: Optional[str] = None


class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class ParsedReceipt(BaseModel):
    merchant: Optional[Merchant] = None
    date: Optional[str] = None           # ISO 8601: YYYY-MM-DD
    invoice_number: Optional[str] = None
    line_items: List[LineItem] = []
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    tip: Optional[float] = None
    discount: Optional[float] = None
    total: Optional[float] = None
    currency: Optional[str] = None       # ISO 4217: USD, EUR, etc.
    payment_method: Optional[str] = None
    notes: Optional[str] = None          # Any extra info Claude picks up


class ParseResponse(BaseModel):
    success: bool
    pages_processed: int
    data: Optional[ParsedReceipt] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


class APIKey(BaseModel):
    id: str
    name: str
    key_preview: str    # e.g. "rp_live_abc...xyz" — never return full key after creation
    created_at: str
    last_used_at: Optional[str] = None
    request_count: int = 0


class NewAPIKeyResponse(BaseModel):
    id: str
    name: str
    key: str            # Full key — only returned ONCE at creation time
    created_at: str
