"""
Products router tests with rollback for non-persistent test data.
Run with: pytest app/tests/test_products.py -v
"""

import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.auth.jwt import create_access_token
from app.database.connection import pool_manager
from app.database.transactions import DB
from app.main import create_app


@pytest_asyncio.fixture
async def app_client():
    """Fixture: running app with HTTP client."""
    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        transport = ASGITransport(app=fresh_app)
        async with AsyncClient(
            transport=transport, base_url="https://testserver"
        ) as client:
            yield client


@pytest_asyncio.fixture
async def db_conn():
    """Fixture: write DB connection inside app lifespan."""
    fresh_app = create_app()
    async with fresh_app.router.lifespan_context(fresh_app):
        async with pool_manager.write_pool.acquire() as conn:
            yield conn


def make_admin_token():
    """Return a signed JWT for an admin user."""
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
    """Return a signed JWT for a regular user."""
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
async def test_list_products(app_client):  # pylint: disable=redefined-outer-name
    """Test listing products returns 200 and a list."""
    response = await app_client.get("/api/v1/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =============================================================================
# CREATE PRODUCT - admin only, POST /api/v1/products/
# =============================================================================
@pytest.mark.asyncio
async def test_create_product_unauthenticated(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test create product fails without authentication."""
    response = await app_client.post(
        "/api/v1/products",
        json={"name_es": "Producto", "name_en": "Product"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_product_forbidden_for_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test create product is forbidden for non-admin users."""
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.post(
        "/api/v1/products",
        json={"name_es": "Producto", "name_en": "Product"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403

    app_client.cookies.clear()


# =============================================================================
# UPDATE PRODUCT - admin only, PUT /api/v1/products/{product_uuid}
# =============================================================================
@pytest.mark.asyncio
async def test_update_product_unauthenticated(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test update product fails without authentication."""
    response = await app_client.put(
        f"/api/v1/products/{uuid.uuid4()}",
        json={"name_es": "Nuevo", "name_en": "New"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_product_forbidden_for_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test update product is forbidden for non-admin users."""
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.put(
        f"/api/v1/products/{uuid.uuid4()}",
        json={"name_es": "Nuevo", "name_en": "New"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403

    app_client.cookies.clear()


# =============================================================================
# DELETE PRODUCT - admin only, DELETE /api/v1/products/{product_uuid}
# =============================================================================
@pytest.mark.asyncio
async def test_delete_product_unauthenticated(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test delete product fails without authentication."""
    response = await app_client.delete(f"/api/v1/products/{uuid.uuid4()}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_product_forbidden_for_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test delete product is forbidden for non-admin users."""
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.delete(
        f"/api/v1/products/{uuid.uuid4()}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403

    app_client.cookies.clear()


# =============================================================================
# ROLLBACK TEST
# =============================================================================
@pytest.mark.asyncio
async def test_create_product_with_rollback(
    db_conn,
):  # pylint: disable=redefined-outer-name
    """Test product creation rolls back cleanly without persisting data."""
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
