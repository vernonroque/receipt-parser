import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services.auth_middleware import _check_quotas, _hourly_counters, _key_cache
from app.main import app

KEY_ID = "test-key-id"


def this_month_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_month_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=32)).isoformat()


@pytest.fixture(autouse=True)
def clear_rate_limit_state():
    _hourly_counters.clear()
    _key_cache.clear()
    yield
    _hourly_counters.clear()
    _key_cache.clear()


# ---- Monthly quota unit tests ----

class TestMonthlyQuota:
    def test_free_tier_under_limit(self):
        _check_quotas(KEY_ID, "free", 499, this_month_iso())

    def test_free_tier_at_limit(self):
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "free", 500, this_month_iso())
        assert exc_info.value.status_code == 429
        assert "Monthly" in exc_info.value.detail

    def test_free_tier_over_limit(self):
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "free", 999, this_month_iso())
        assert exc_info.value.status_code == 429

    def test_free_tier_resets_when_reset_at_is_last_month(self):
        # count=999 but reset_at from last month → effective_count=0 → no block
        _check_quotas(KEY_ID, "free", 999, last_month_iso())

    def test_invalid_reset_at_defaults_to_current_month(self):
        # Malformed date → reset_dt falls back to now_utc → count treated as current
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "free", 500, "not-a-valid-date")
        assert exc_info.value.status_code == 429

    def test_none_reset_at_defaults_to_current_month(self):
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "free", 500, "")
        assert exc_info.value.status_code == 429

    @pytest.mark.parametrize("plan,limit", [
        ("starter", 5_000),
        ("pro", 25_000),
        ("business", 150_000),
    ])
    def test_plan_limits_at_boundary(self, plan, limit):
        _check_quotas(KEY_ID, plan, limit - 1, this_month_iso())  # one under → ok
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, plan, limit, this_month_iso())   # at limit → 429
        assert exc_info.value.status_code == 429

    @pytest.mark.parametrize("plan,limit", [
        ("starter", 5_000),
        ("pro", 25_000),
        ("business", 150_000),
    ])
    def test_plan_limits_reset_correctly(self, plan, limit):
        # High count from last month should be forgiven
        _check_quotas(KEY_ID, plan, limit, last_month_iso())


# ---- Hourly rate limit unit tests ----

class TestHourlyRateLimit:
    def test_free_tier_hourly_limit_enforced(self):
        reset_iso = this_month_iso()
        for _ in range(100):
            _check_quotas(KEY_ID, "free", 0, reset_iso)
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "free", 0, reset_iso)  # 101st call
        assert exc_info.value.status_code == 429
        assert "Hourly" in exc_info.value.detail

    def test_business_tier_has_no_hourly_limit(self):
        reset_iso = this_month_iso()
        for _ in range(200):
            _check_quotas(KEY_ID, "business", 0, reset_iso)

    def test_hourly_counters_are_isolated_per_key(self):
        reset_iso = this_month_iso()
        for _ in range(100):
            _check_quotas("key-a", "free", 0, reset_iso)
        # key-b has its own counter; this should be its first call
        _check_quotas("key-b", "free", 0, reset_iso)

    def test_starter_tier_hourly_limit(self):
        reset_iso = this_month_iso()
        for _ in range(500):
            _check_quotas(KEY_ID, "starter", 0, reset_iso)
        with pytest.raises(HTTPException) as exc_info:
            _check_quotas(KEY_ID, "starter", 0, reset_iso)
        assert exc_info.value.status_code == 429


# ---- Integration smoke test (Supabase mocked) ----

class TestIntegrationQuota:
    def _make_supabase_mock(self, monthly_count: int, plan: str = "free") -> MagicMock:
        # MagicMock (not AsyncMock) so chained attribute calls return regular mocks,
        # not coroutines; only .execute() at the end of the chain needs to be async.
        mock_supabase = MagicMock()
        mock_result = MagicMock()
        mock_result.data = {
            "id": KEY_ID,
            "is_active": True,
            "plan": plan,
            "monthly_request_count": monthly_count,
            "monthly_reset_at": this_month_iso(),
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=mock_result
        )
        mock_supabase.rpc.return_value.execute = AsyncMock(return_value=None)
        return mock_supabase

    def test_parse_returns_429_when_monthly_quota_exceeded(self):
        client = TestClient(app)
        app.state.supabase = self._make_supabase_mock(monthly_count=500, plan="free")
        try:
            res = client.post(
                "/api/parse",
                files={"file": ("r.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")},
                headers={"Authorization": "Bearer any-key-triggers-db-lookup"},
            )
        finally:
            app.state.supabase = None

        assert res.status_code == 429
        assert "Monthly" in res.json().get("detail", "")

    def test_parse_proceeds_when_under_quota(self):
        # 499 requests used — should get past quota check (may fail later for other reasons,
        # e.g. PIL can't parse the fake bytes, but the important thing is no 429).
        client = TestClient(app, raise_server_exceptions=False)
        app.state.supabase = self._make_supabase_mock(monthly_count=499, plan="free")
        try:
            res = client.post(
                "/api/parse",
                files={"file": ("r.jpg", b"\xff\xd8\xff" + b"x" * 100, "image/jpeg")},
                headers={"Authorization": "Bearer any-key-triggers-db-lookup"},
            )
        finally:
            app.state.supabase = None

        assert res.status_code != 429
