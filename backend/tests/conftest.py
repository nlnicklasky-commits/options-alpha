"""Shared test fixtures."""

import pytest


@pytest.fixture
async def client():
    """Async test client for FastAPI app.

    Lazily imports app to avoid import errors when DB dependencies
    are not installed (e.g., asyncpg).
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
