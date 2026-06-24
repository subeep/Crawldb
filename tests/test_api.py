"""Tests for API endpoints (requires running services)."""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_api_docs_accessible():
    """Test that the FastAPI docs endpoint returns 200."""
    # This test only validates the app can be instantiated
    from crawldb.api.app import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/docs")
        # Docs should return 200 even without DB connections
        assert response.status_code == 200
