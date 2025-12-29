import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def initialized_app():
    async with app.router.lifespan_context(app):
        yield app


@pytest.mark.asyncio
async def test_basic_health_endpoint(initialized_app):
    transport = ASGITransport(app=initialized_app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "Proveo API"


@pytest.mark.asyncio
async def test_database_health_endpoint(initialized_app):
    transport = ASGITransport(app=initialized_app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health/database")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["status"] in {"healthy", "unhealthy"}
    assert "timestamp" in data

    if data["status"] == "healthy":
        assert "pool" in data
        assert "size" in data["pool"]
        assert "max_size" in data["pool"]
