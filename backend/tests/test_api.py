"""API endpoint smoke tests.

Verifies each endpoint returns valid status codes with valid response schemas.
These tests hit the real app and require a running database connection.
Endpoints that require DB data may return empty results or 404s,
which is fine for smoke testing — we just verify no 500 errors.

Skipped automatically when asyncpg is not installed (local dev without DB deps).
"""

import pytest

try:
    import asyncpg  # noqa: F401
    HAS_DB_DEPS = True
except ImportError:
    HAS_DB_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DB_DEPS, reason="asyncpg not installed")

from httpx import AsyncClient


@pytest.mark.asyncio
class TestHealthEndpoints:
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    async def test_health_data(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


@pytest.mark.asyncio
class TestSignalsEndpoints:
    async def test_signals_returns_list(self, client: AsyncClient) -> None:
        resp = await client.get("/api/signals?n=5")
        # May return empty list if no model/data, but should not 500
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_signals_regime(self, client: AsyncClient) -> None:
        resp = await client.get("/api/signals/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
        assert data["regime"] in ("BULL", "BEAR", "CHOPPY")


@pytest.mark.asyncio
class TestScoreEndpoints:
    async def test_score_nonexistent_stock(self, client: AsyncClient) -> None:
        resp = await client.get("/api/score/ZZZZZZ")
        assert resp.status_code == 404

    async def test_chart_nonexistent_stock(self, client: AsyncClient) -> None:
        resp = await client.get("/api/score/ZZZZZZ/chart")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestBacktestEndpoints:
    async def test_get_nonexistent_backtest(self, client: AsyncClient) -> None:
        resp = await client.get("/api/backtest/999999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestJournalEndpoints:
    async def test_list_journal(self, client: AsyncClient) -> None:
        resp = await client.get("/api/journal")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestOptionsEndpoints:
    async def test_options_nonexistent_stock(self, client: AsyncClient) -> None:
        resp = await client.get("/api/options/ZZZZZZ")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestPipelineEndpoints:
    async def test_pipeline_status(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pipeline/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_pipeline_job_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/api/pipeline/status/nonexistent_job")
        assert resp.status_code == 404
