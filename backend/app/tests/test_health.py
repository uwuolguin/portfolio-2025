"""Health endpoint tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import create_app


@pytest_asyncio.fixture
async def initialized_app():
    """Create a fresh application instance for each test."""
    fresh_app = create_app()

    async with fresh_app.router.lifespan_context(fresh_app):
        yield fresh_app


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_basic_health_endpoint(initialized_app):
    """Verify the basic health endpoint returns a healthy response."""
    transport = ASGITransport(app=initialized_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "Proveo API"


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_database_health_endpoint(initialized_app):
    """Verify the database health endpoint returns a valid response."""
    transport = ASGITransport(app=initialized_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/v1/health/database")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data
    assert data["status"] in {"healthy", "unhealthy"}
    assert "timestamp" in data

    if data["status"] == "healthy":
        assert "pool" in data
        assert "max_size" in data["pool"]
        assert "read_size" in data["pool"]
        assert "replica_available" in data["pool"]
        assert "write_size" in data["pool"]