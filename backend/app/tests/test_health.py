import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_basic_health_endpoint():
    """Test that basic health endpoint returns 200 and correct status"""
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "Proveo API"


@pytest.mark.asyncio
async def test_database_health_endpoint():
    """Test that database health endpoint returns connection info"""
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health/database")
        
        # Should return 200 even if database is unavailable (for monitoring)
        assert response.status_code == 200
        data = response.json()
        
        # Should have status field
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]
        
        # Should have timestamp
        assert "timestamp" in data
        
        # If healthy, should have pool info
        if data["status"] == "healthy":
            assert "pool" in data
            assert "size" in data["pool"]
            assert "max_size" in data["pool"]