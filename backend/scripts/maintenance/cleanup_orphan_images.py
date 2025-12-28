"""
python -m app.services.create_admin
docker compose exec backend python -m app.services.create_admin
"""
import asyncio
import asyncpg
import uuid
import sys
from contextlib import asynccontextmanager

from app.config import settings
from app.auth.jwt import get_password_hash


@asynccontextmanager
async def get_conn():
    conn = await asyncpg.connect(settings.alembic_database_url)
    try:
        yield conn
    finally:
        await conn.close()


async def create_admin_user():
    """Create the initial admin user if not exists"""

    admin_email = input("Enter admin email: ").strip()
    admin_password = input("Enter admin password (min 8 chars): ").strip()

    if len(admin_password) < 8:
        print("❌ Password must be at least 8 characters")
        return False

    admin_name = input("Enter admin name (default: Admin): ").strip() or "Admin"

    print("\n📋 Creating admin user:")
    print(f"   Email: {admin_email}")
    print(f"   Name: {admin_name}")
    print("   Role: admin")

    confirm = input("\nProceed? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("❌ Cancelled")
        return False

    try:
        async with get_conn() as conn:
            existing = await conn.fetchval(
                "SELECT uuid FROM proveo.users WHERE email = $1",
                admin_email,
            )

            if existing:
                await conn.execute(
                    """
                    UPDATE proveo.users
                    SET role = 'admin',
                        email_verified = true,
                        verification_token = NULL,
                        verification_token_expires = NULL,
                        hashed_password = $1
                    WHERE email = $2
                    """,
                    get_password_hash(admin_password),
                    admin_email,
                )
                print(f"✅ Updated existing user to admin: {admin_email}")
            else:
                user_uuid = str(uuid.uuid4())
                hashed_password = get_password_hash(admin_password)

                await conn.execute(
                    """
                    INSERT INTO proveo.users
                    (uuid, name, email, hashed_password, role, email_verified,
                     verification_token, verification_token_expires)
                    VALUES ($1, $2, $3, $4, 'admin', true, NULL, NULL)
                    """,
                    user_uuid,
                    admin_name,
                    admin_email,
                    hashed_password,
                )
                print(f"✅ Created new admin user: {admin_email}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("🔐 Admin User Setup\n")
    success = asyncio.run(create_admin_user())
    sys.exit(0 if success else 1)
