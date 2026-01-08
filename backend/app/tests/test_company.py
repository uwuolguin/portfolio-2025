"""
Companies router tests with rollback for non-persistent test data.
Run with: pytest app/tests/test_companies.py -v

REQUIRES:
- transaction() function updated with force_rollback parameter
- DB.create_company updated with force_rollback parameter
- Seeded data: communes, products, users with companies
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


def make_user_token(user_uuid: str = None, verified: bool = True):
    """Create regular user JWT token"""
    jwt_payload = {
        "sub": user_uuid or str(uuid.uuid4()),
        "name": "User",
        "email": "user@test.com",
        "role": "user",
        "email_verified": verified,
        "created_at": "2025-01-01T00:00:00",
    }
    return create_access_token(data=jwt_payload, expires_delta=timedelta(minutes=30))


# =============================================================================
# SEARCH COMPANIES - public endpoint (read-only)
# =============================================================================
@pytest.mark.asyncio
async def test_search_companies(app_client):
    response = await app_client.get("/api/v1/companies/search")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_search_companies_with_query(app_client):
    response = await app_client.get("/api/v1/companies/search", params={"q": "test"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_search_companies_with_filters(app_client):
    response = await app_client.get(
        "/api/v1/companies/search",
        params={"commune": "Santiago Centro", "product": "Tecnología", "lang": "es"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =============================================================================
# GET COMPANY BY UUID - public endpoint
# =============================================================================
@pytest.mark.asyncio
async def test_get_company_not_found(app_client):
    response = await app_client.get(f"/api/v1/companies/{uuid.uuid4()}")
    assert response.status_code == 404


# =============================================================================
# GET MY COMPANY
# =============================================================================
@pytest.mark.asyncio
async def test_get_my_company_unauthenticated(app_client):
    response = await app_client.get("/api/v1/companies/user/my-company")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_company_not_found(app_client):
    token = make_user_token()
    app_client.cookies.set("access_token", token)

    response = await app_client.get("/api/v1/companies/user/my-company")
    assert response.status_code == 404


# =============================================================================
# CREATE COMPANY
# =============================================================================
@pytest.mark.asyncio
async def test_create_company_unauthenticated(app_client):
    response = await app_client.post(
        "/api/v1/companies",
        data={
            "name": "Test",
            "commune_name": "Santiago",
            "product_name": "Tech",
            "address": "Test 123",
            "phone": "+56911111111",
            "email": "test@test.com",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_company_unverified_email(app_client):
    token = make_user_token(verified=False)
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.post(
        "/api/v1/companies",
        data={
            "name": "Test",
            "commune_name": "Santiago",
            "product_name": "Tech",
            "address": "Test 123",
            "phone": "+56911111111",
            "email": "test@test.com",
            "description_es": "Descripcion",
            "lang": "es",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# UPDATE MY COMPANY
# =============================================================================
@pytest.mark.asyncio
async def test_update_my_company_unauthenticated(app_client):
    response = await app_client.patch(
        "/api/v1/companies/user/my-company", data={"name": "Updated Name"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_my_company_unverified_email(app_client):
    token = make_user_token(verified=False)
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.patch(
        "/api/v1/companies/user/my-company",
        data={"name": "Updated Name"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# DELETE MY COMPANY
# =============================================================================
@pytest.mark.asyncio
async def test_delete_my_company_unauthenticated(app_client):
    response = await app_client.delete("/api/v1/companies/user/my-company")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_my_company_unverified_email(app_client):
    token = make_user_token(verified=False)
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.delete(
        "/api/v1/companies/user/my-company",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# ADMIN LIST COMPANIES
# =============================================================================
@pytest.mark.asyncio
async def test_admin_list_companies_unauthenticated(app_client):
    response = await app_client.get(
        "/api/v1/companies/admin/all-companies/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_companies_forbidden_for_user(app_client):
    token = make_user_token()
    app_client.cookies.set("access_token", token)

    response = await app_client.get(
        "/api/v1/companies/admin/all-companies/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_companies_success(app_client):
    token = make_admin_token()
    app_client.cookies.set("access_token", token)

    response = await app_client.get(
        "/api/v1/companies/admin/all-companies/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# =============================================================================
# ADMIN DELETE COMPANY
# =============================================================================
@pytest.mark.asyncio
async def test_admin_delete_company_unauthenticated(app_client):
    response = await app_client.delete(
        f"/api/v1/companies/admin/companies/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf"
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_delete_company_forbidden_for_user(app_client):
    token = make_user_token()
    csrf = "test-csrf"

    app_client.cookies.set("access_token", token)
    app_client.cookies.set("csrf_token", csrf)

    response = await app_client.delete(
        f"/api/v1/companies/admin/companies/{uuid.uuid4()}/use-postman-or-similar-to-bypass-csrf",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


# =============================================================================
# ROLLBACK TEST
# =============================================================================
@pytest.mark.asyncio
async def test_create_company_with_rollback(db_conn):
    communes = await DB.get_all_communes(conn=db_conn)
    products = await DB.get_all_products(conn=db_conn)

    if not communes or not products:
        pytest.skip("Requires seeded communes and products")

    commune_uuid = communes[0].uuid
    product_uuid = products[0].uuid

    user_uuid = uuid.uuid4()
    company_uuid = uuid.uuid4()
    unique_email = f"company_test_{uuid.uuid4().hex[:8]}@test.com"
    unique_name = f"Rollback Company {uuid.uuid4().hex[:8]}"

    from app.database.transactions import transaction
    from app.auth.jwt import get_password_hash
    from app.auth.csrf import generate_csrf_token
    from datetime import datetime, timezone
    from app.config import settings

    async with transaction(db_conn, force_rollback=True):
        hashed_password = get_password_hash("TestPass123!")
        verification_token = generate_csrf_token()
        token_expires = datetime.now(timezone.utc) + timedelta(
            hours=settings.verification_token_email_time
        )

        user_query = """
            INSERT INTO proveo.users
                (uuid, name, email, hashed_password, role, verification_token, verification_token_expires)
            VALUES ($1, $2, $3, $4, 'user', $5, $6)
            RETURNING uuid
        """
        await db_conn.fetchrow(
            user_query,
            user_uuid,
            "Company Test User",
            unique_email,
            hashed_password,
            verification_token,
            token_expires,
        )

        company_query = """
            INSERT INTO proveo.companies (
                uuid, user_uuid, product_uuid, commune_uuid,
                name, description_es, description_en,
                address, phone, email, image_url, image_extension
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING uuid
        """
        await db_conn.fetchrow(
            company_query,
            company_uuid,
            user_uuid,
            product_uuid,
            commune_uuid,
            unique_name,
            "Descripción",
            "Description",
            "Address",
            "+56911111111",
            "rollback@test.com",
            "img",
            ".jpg",
        )

    assert await DB.get_user_by_email(conn=db_conn, email=unique_email) is None
    assert await DB.get_company_by_uuid(conn=db_conn, company_uuid=company_uuid) is None
