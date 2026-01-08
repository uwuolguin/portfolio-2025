"""
Products router tests with rollback for non-persistent test data.
Run with: pytest app/tests/test_products.py -v

REQUIRES:
- transaction() function updated with force_rollback parameter
- DB.create_product updated with force_rollback parameter
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
        "created_at": "2025-01-01T00:00:00",
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
        "created_at": "2025-01-01T00:00:00",
    }
    return create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=30))


# =============================================================================
# LIST PRODUCTS - public endpoint (read-only)
# =============================================================================
@pytest.mark.asyncio
async def test_list_products(app_client):
    response = await app_client.get("/api/v1/products/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =============================================================================
# CREATE PRODUCT - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_create_product_unauthenticated(app_client):
    response = await app_client.post(
        "/api/v1/products/use-postman-or-similar-to-bypass-csrf",
        json={"name_es": "Producto", "name_en": "Product"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_product_forbidden_for_user(app_client):
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.post(
        "/api/v1/products/use-postman-or-similar-to-bypass-csrf",
        json={"name_es": "Producto", "name_en": "Product"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# UPDATE PRODUCT - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_update_product_unauthenticated(app_client):
    response = await app_client.put(
        f"/api/v1/products/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        json={"name_es": "Nuevo", "name_en": "New"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_product_forbidden_for_user(app_client):
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.put(
        f"/api/v1/products/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        json={"name_es": "Nuevo", "name_en": "New"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# DELETE PRODUCT - admin only
# =============================================================================
@pytest.mark.asyncio
async def test_delete_product_unauthenticated(app_client):
    response = await app_client.delete(
        f"/api/v1/products/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_product_forbidden_for_user(app_client):
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.delete(
        f"/api/v1/products/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# ROLLBACK TEST - Direct DB product creation (does not persist)
# =============================================================================
@pytest.mark.asyncio
async def test_create_product_with_rollback(db_conn):
    unique_suffix = uuid.uuid4().hex[:8]
    name_es = f"Producto Rollback {unique_suffix}"
    name_en = f"Rollback Product {unique_suffix}"

    product = await DB.create_product(
        conn=db_conn,
        name_es=name_es,
        name_en=name_en,
        force_rollback=True,
    )

    assert product is not None
    assert product.name_es == name_es
    assert product.name_en == name_en

    all_products = await DB.get_all_products(conn=db_conn)
    names_es = [p.name_es for p in all_products]
    assert name_es not in names_es
