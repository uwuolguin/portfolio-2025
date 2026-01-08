"""
Communes router tests with rollback for non-persistent test data.
Run with: pytest app/tests/test_communes.py -v

REQUIRES: 
- transaction() function updated with force_rollback parameter
- DB.create_commune updated with force_rollback parameter
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.database.connection import pool_manager
from app.database.transactions import DB
from app.auth.jwt import create_access_token
from datetime import timedelta
import uuid


@pytest_asyncio.fixture
async def app_client():
    """Create app and client for tests"""
    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        transport = ASGITransport(app=fresh_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


@pytest_asyncio.fixture
async def db_conn():
    """Get a database connection for direct DB operations"""
    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        async with pool_manager.write_pool.acquire() as conn:
            yield conn


def make_admin_token():
    """Create admin JWT token"""
    jwt_payload = {
        "sub": str(uuid.uuid4()),
        "name": "Admin",
        "email": "admin@test.com",
        "role": "admin",
        "email_verified": True,
        "created_at": "2025-01-01T00:00:00"
    }
    return create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=30))


def make_user_token():
    """Create regular user JWT token"""
    jwt_payload = {
        "sub": str(uuid.uuid4()),
        "name": "User",
        "email": "user@test.com",
        "role": "user",
        "email_verified": True,
        "created_at": "2025-01-01T00:00:00"
    }
    return create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=30))


# =============================================================================
# LIST COMMUNES - public endpoint (read-only)
# =============================================================================
@pytest.mark.asyncio
async def test_list_communes(app_client):
    """Test listing communes returns 200 and list"""
    response = await app_client.get("/api/v1/communes/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =============================================================================
# CREATE COMMUNE - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_create_commune_unauthenticated(app_client):
    """Test create commune fails without auth"""
    response = await app_client.post(
        "/api/v1/communes/use-postman-or-similar-to-bypass-csrf",
        json={"name": "Test Commune"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_commune_forbidden_for_user(app_client):
    """Test create commune forbidden for non-admin"""
    token = make_user_token()
    csrf = "test-csrf"
    
    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)
    
    response = await app_client.post(
        "/api/v1/communes/use-postman-or-similar-to-bypass-csrf",
        json={"name": "Test Commune"},
        headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403
    
    # Clean up for test isolation
    app_client.cookies.clear()


# =============================================================================
# UPDATE COMMUNE - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_update_commune_unauthenticated(app_client):
    """Test update commune fails without auth"""
    response = await app_client.put(
        f"/api/v1/communes/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        json={"name": "Updated Name"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_commune_forbidden_for_user(app_client):
    """Test update commune forbidden for non-admin"""
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)
    
    response = await app_client.put(
        f"/api/v1/communes/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        json={"name": "Updated Name"},
        headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403
    
    # Clean up for test isolation
    app_client.cookies.clear()


# =============================================================================
# DELETE COMMUNE - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_delete_commune_unauthenticated(app_client):
    """Test delete commune fails without auth"""
    response = await app_client.delete(
        f"/api/v1/communes/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_commune_forbidden_for_user(app_client):
    """Test delete commune forbidden for non-admin"""
    token = make_user_token()
    csrf = "test-csrf"
    
    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)
    
    response = await app_client.delete(
        f"/api/v1/communes/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403
    
    # Clean up for test isolation
    app_client.cookies.clear()


# =============================================================================
# ROLLBACK TEST - Direct DB commune creation (does not persist)
# =============================================================================
@pytest.mark.asyncio
async def test_create_commune_with_rollback(db_conn):
    """
    Test that we can create a commune with force_rollback=True
    and it doesn't persist in the database.
    """
    unique_name = f"Rollback Commune {uuid.uuid4().hex[:8]}"
    
    # Create commune with rollback
    commune = await DB.create_commune(
        conn=db_conn,
        name=unique_name,
        force_rollback=True,
    )
    
    assert commune is not None
    assert commune.name == unique_name
    
    # Verify commune does NOT exist in DB (was rolled back)
    all_communes = await DB.get_all_communes(conn=db_conn)
    names = [c.name for c in all_communes]
    assert unique_name not in names, "Commune should not persist after rollback"
