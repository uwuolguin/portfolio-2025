"""
Seed test data: 16 users with companies + 1 admin
Usage:
  docker compose exec backend python -m scripts.database.seed_test_data
"""

import asyncio
import asyncpg
import httpx
from io import BytesIO
from contextlib import asynccontextmanager
import structlog
import uuid

from app.config import settings
from app.database.transactions import DB
from app.services.image_service_client import image_service_client

logger = structlog.get_logger(__name__)

TEST_IMAGES = [
    "test1.jpg",
    "test2.jpg",
    "test3.jpg",
]

COMPANY_TEMPLATES = [
    {
        "name": f"Test Company {i+1}",
        "description_es": "Empresa de prueba",
        "description_en": "Test company",
        "address": "Test Address 123",
        "phone": "+56 9 1111 1111",
        "email": f"company{i+1}@test.com",
    }
    for i in range(16)
]

TEST_USERS = [
    {
        "name": f"Test User {i+1}",
        "email": f"testuser{i+1:02d}@proveo.com",
        "password": "TestPass123!",
    }
    for i in range(16)
]


@asynccontextmanager
async def get_conn():
    conn = await asyncpg.connect(settings.alembic_database_url)
    try:
        yield conn
    finally:
        await conn.close()


async def fetch_test_image_bytes(image_name: str) -> BytesIO:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"http://nginx/files/test_pictures/{image_name}"
        )
        response.raise_for_status()
        image_bytes = BytesIO(response.content)
        image_bytes.seek(0)
        return image_bytes


async def seed_test_data() -> None:
    async with get_conn() as conn:
        try:
            logger.info("seed_start")

            try:
                commune_1 = await DB.create_commune(conn, "Santiago Centro")
            except ValueError:
                commune_1 = await conn.fetchrow(
                    "SELECT * FROM proveo.communes WHERE name = 'Santiago Centro'"
                )

            try:
                commune_2 = await DB.create_commune(conn, "Providencia")
            except ValueError:
                commune_2 = await conn.fetchrow(
                    "SELECT * FROM proveo.communes WHERE name = 'Providencia'"
                )

            try:
                product_1 = await DB.create_product(conn, "Tecnología", "Technology")
            except ValueError:
                product_1 = await conn.fetchrow(
                    "SELECT * FROM proveo.products WHERE name_es = 'Tecnología'"
                )

            try:
                product_2 = await DB.create_product(conn, "Alimentos", "Food")
            except ValueError:
                product_2 = await conn.fetchrow(
                    "SELECT * FROM proveo.products WHERE name_es = 'Alimentos'"
                )

            for i, user_data in enumerate(TEST_USERS):
                try:
                    user = await DB.create_user(
                        conn=conn,
                        name=user_data["name"],
                        email=user_data["email"],
                        password=user_data["password"],
                    )

                    await conn.execute(
                        """
                        UPDATE proveo.users
                        SET email_verified = TRUE,
                            verification_token = NULL,
                            verification_token_expires = NULL
                        WHERE uuid = $1
                        """,
                        user.uuid,
                    )

                    image_name = TEST_IMAGES[i % len(TEST_IMAGES)]
                    image_stream = await fetch_test_image_bytes(image_name)

                    company_uuid = uuid.uuid4()

                    upload_result = await image_service_client.upload_image_streaming(
                        file_obj=image_stream,
                        company_id=str(company_uuid),
                        content_type="image/jpeg",
                        extension=".jpg",
                        user_id=str(user.uuid),
                    )

                    product_uuid = product_1.uuid if i < 8 else product_2.uuid
                    commune_uuid = commune_1.uuid if i < 8 else commune_2.uuid
                    template = COMPANY_TEMPLATES[i]

                    await DB.create_company(
                        conn=conn,
                        company_uuid=company_uuid,
                        user_uuid=user.uuid,
                        product_uuid=product_uuid,
                        commune_uuid=commune_uuid,
                        name=template["name"],
                        description_es=template["description_es"],
                        description_en=template["description_en"],
                        address=template["address"],
                        phone=template["phone"],
                        email=template["email"],
                        image_url=upload_result["image_id"],
                        image_extension=upload_result["extension"],
                    )

                except ValueError:
                    continue

            admin = await conn.fetchrow(
                "SELECT * FROM proveo.users WHERE email = 'admin_test@mail.com'"
            )

            if not admin:
                await DB.create_user(
                    conn=conn,
                    name="Admin User",
                    email="admin_test@mail.com",
                    password="password",
                )

            await conn.execute(
                """
                UPDATE proveo.users
                SET role = 'admin',
                    email_verified = TRUE,
                    verification_token = NULL,
                    verification_token_expires = NULL
                WHERE email = 'admin_test@mail.com'
                """
            )

            await conn.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search"
            )

            print("✅ Seeding completed successfully")

        except Exception:
            logger.error("seed_failed", exc_info=True)
            raise


if __name__ == "__main__":
    asyncio.run(seed_test_data())