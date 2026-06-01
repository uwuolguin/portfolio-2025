"""
Users router tests (restored + fixed).

Run with:
    pytest app/tests/test_users.py -v
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


# =============================================================================
# FIXTURES
# =============================================================================
@pytest_asyncio.fixture
async def app_client():
    """Fixture: running app with HTTP client."""
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="https://testserver",
        ) as client:
            yield client, app


@pytest_asyncio.fixture
async def db_conn():
    """Fixture: write DB connection inside app lifespan."""
    app = create_app()
    async with app.router.lifespan_context(app):
        async with pool_manager.write_pool.acquire() as conn:
            yield conn


# =============================================================================
# SIGNUP
# =============================================================================
@pytest.mark.asyncio
async def test_signup_invalid_email(app_client):  # pylint: disable=redefined-outer-name
    """Test signup rejects invalid email format."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/signup",
        json={"name": "Test", "email": "bad-email", "password": "TestPass123!"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_short_password(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test signup rejects passwords that are too short."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/signup",
        json={"name": "Test", "email": "test@test.com", "password": "short"},
    )
    assert response.status_code == 422


# =============================================================================
# LOGIN
# =============================================================================
@pytest.mark.asyncio
async def test_login_wrong_password(app_client):  # pylint: disable=redefined-outer-name
    """Test login fails with wrong password."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/login",
        json={
            "email": "admin_test@mail.com",
            "password": "wrongpassword",
            "lang": "en",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test login fails for a non-existent user."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/login",
        json={"email": "nobody@nowhere.com", "password": "password", "lang": "en"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_success(app_client):  # pylint: disable=redefined-outer-name
    """Test successful login returns access token and CSRF token."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/login",
        json={"email": "admin_test@mail.com", "password": "password", "lang": "en"},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "csrf_token" in response.json()


# =============================================================================
# LOGOUT
# =============================================================================
@pytest.mark.asyncio
async def test_logout_success(app_client):  # pylint: disable=redefined-outer-name
    """Test logout succeeds for an authenticated user."""
    client, _ = app_client

    payload = {
        "sub": str(uuid.uuid4()),
        "email": "test@test.com",
        "name": "Test User",
        "role": "user",
        "email_verified": True,
        "created_at": "2025-01-01T00:00:00",
    }
    token = create_access_token(payload, timedelta(minutes=30))
    csrf = "csrf-test"

    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf)

    response = await client.post(
        "/api/v1/users/logout",
        headers={"X-CSRF-Token": csrf},
        json={"lang": "es"},
    )
    assert response.status_code == 200


# =============================================================================
# ME
# =============================================================================
@pytest.mark.asyncio
async def test_me_unauthenticated(app_client):  # pylint: disable=redefined-outer-name
    """Test /me endpoint returns 401 for unauthenticated requests."""
    client, _ = app_client
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(app_client):  # pylint: disable=redefined-outer-name
    """Test /me endpoint returns user data for authenticated requests."""
    client, _ = app_client

    payload = {
        "sub": str(uuid.uuid4()),
        "email": "test@test.com",
        "name": "Test User",
        "role": "user",
        "email_verified": True,
        "created_at": "2025-01-01T00:00:00",
    }
    token = create_access_token(payload, timedelta(minutes=30))
    client.cookies.set("access_token", token)

    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@test.com"


# =============================================================================
# EMAIL VERIFICATION
# =============================================================================
@pytest.mark.asyncio
async def test_verify_email_invalid_token(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test email verification fails for an invalid token."""
    client, _ = app_client
    response = await client.get("/api/v1/users/verify-email/invalid-token")
    assert response.status_code == 200
    assert "Verification Failed" in response.text


@pytest.mark.asyncio
async def test_resend_verification_user_not_found(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test resend verification fails for a non-existent user."""
    client, _ = app_client
    response = await client.post(
        "/api/v1/users/resend-verification",
        params={"email": "ghost@nowhere.com"},
    )
    assert response.status_code == 400


# =============================================================================
# DELETE ME
# =============================================================================
@pytest.mark.asyncio
async def test_delete_me_unauthenticated(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test delete me fails without authentication."""
    client, _ = app_client
    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_me_missing_csrf(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test delete me fails when CSRF token is missing."""
    client, _ = app_client

    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "user"},
        timedelta(minutes=30),
    )
    client.cookies.set("access_token", token)

    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 403


# =============================================================================
# ADMIN - GET /api/v1/users/admin/all-users
#         DELETE /api/v1/users/admin/users/{user_id}
# =============================================================================
ADMIN_LIST_PATH = "/api/v1/users/admin/all-users"
ADMIN_DELETE_PATH = "/api/v1/users/admin/users/{user_id}"


@pytest.mark.asyncio
async def test_admin_get_users_unauthenticated(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test admin get users fails without authentication."""
    client, _ = app_client
    response = await client.get(ADMIN_LIST_PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_get_users_forbidden_for_regular_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test admin get users is forbidden for regular users."""
    client, _ = app_client

    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "user"},
        timedelta(minutes=30),
    )
    client.cookies.set("access_token", token)

    response = await client.get(ADMIN_LIST_PATH)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_delete_user_forbidden_for_regular_user(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test admin delete user is forbidden for regular users."""
    client, _ = app_client

    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "user"},
        timedelta(minutes=30),
    )
    csrf = "csrf-test"

    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf)

    response = await client.delete(
        ADMIN_DELETE_PATH.format(user_id=uuid.uuid4()),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_delete_user_success_not_found(
    app_client,
):  # pylint: disable=redefined-outer-name
    """Test admin delete returns 404 for a non-existent user."""
    client, _ = app_client

    token = create_access_token(
        {"sub": str(uuid.uuid4()), "role": "admin"},
        timedelta(minutes=30),
    )
    csrf = "csrf-test"

    client.cookies.set("access_token", token)
    client.cookies.set("csrf_token", csrf)

    response = await client.delete(
        ADMIN_DELETE_PATH.format(user_id=uuid.uuid4()),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 404


# =============================================================================
# DB ROLLBACK TEST
# =============================================================================
@pytest.mark.asyncio
async def test_create_user_with_rollback(
    db_conn,
):  # pylint: disable=redefined-outer-name
    """Test user creation rolls back cleanly without persisting data."""
    email = f"rollback_{uuid.uuid4().hex[:8]}@test.com"

    user = await DB.create_user(
        conn=db_conn,
        name="Rollback User",
        email=email,
        password="TestPass123!",
        force_rollback=True,
    )

    assert user is not None

    check = await DB.get_user_by_email(conn=db_conn, email=email)
    assert check is None
