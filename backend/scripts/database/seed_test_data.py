"""
Seed test data: 16 users with companies + 1 admin
Usage:
  python -m app.services.testing_setup_users_data
  docker compose exec backend python -m app.services.testing_setup_users_data
"""
import asyncio
import asyncpg
import httpx
from io import BytesIO
from app.config import settings
from app.database.transactions import DB
from app.services.image_service_client import image_service_client
import structlog
import uuid

logger = structlog.get_logger(__name__)


async def fetch_test_image_bytes(image_name: str) -> BytesIO:
    """Fetch test image from Nginx static files"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"http://nginx/files/test_pictures/{image_name}")
        response.raise_for_status()
        image_bytes = BytesIO(response.content)
        image_bytes.seek(0)
        return image_bytes


async def seed_test_data():
    """
    Seed test data using proper DB transactions and image service client.
    Creates 16 test users with companies and necessary communes/products.
    """
    async with asyncpg.connect(settings.alembic_database_url) as conn:
        try:
            logger.info("seed_start", message="Starting test data seeding")
            
            logger.info("creating_communes")
            commune_1 = await DB.create_commune(conn, "Santiago Centro")
            commune_2 = await DB.create_commune(conn, "Providencia")
            logger.info("communes_created", commune_1=commune_1.name, commune_2=commune_2.name)
            
            logger.info("creating_products")
            product_1 = await DB.create_product(conn, "Tecnología", "Technology")
            product_2 = await DB.create_product(conn, "Alimentos", "Food")
            logger.info("products_created", product_1_es=product_1.name_es, product_2_es=product_2.name_es)
            
            for i, user_data in enumerate(TEST_USERS):
                logger.info("processing_user", index=i+1, email=user_data["email"])
                
                try:
                    user = await DB.create_user(
                        conn=conn,
                        name=user_data["name"],
                        email=user_data["email"],
                        password=user_data["password"]
                    )
                    
                    await conn.execute(
                        """
                        UPDATE proveo.users 
                        SET email_verified = TRUE,
                            verification_token = NULL,
                            verification_token_expires = NULL
                        WHERE uuid = $1
                        """,
                        user.uuid
                    )
                    logger.info("user_created_and_verified", user_uuid=str(user.uuid), email=user.email)
                    
                    company_template = COMPANY_TEMPLATES[i]
                    image_index = i % len(TEST_IMAGES)
                    test_image_name = TEST_IMAGES[image_index]
                    
                    logger.info("uploading_image", image=test_image_name, user_uuid=str(user.uuid))
                    image_stream = await fetch_test_image_bytes(test_image_name)
                    
                    company_uuid = uuid.uuid4()
                    upload_result = await image_service_client.upload_image_streaming(
                        file_obj=image_stream,
                        company_id=str(company_uuid),
                        content_type="image/jpeg",
                        extension=".jpg",
                        user_id=str(user.uuid)
                    )
                    
                    image_id = upload_result["image_id"]
                    image_ext = upload_result["extension"]
                    logger.info("image_uploaded", image_id=image_id, nsfw_checked=upload_result["nsfw_checked"])
                    
                    product_uuid = product_1.uuid if i < 8 else product_2.uuid
                    commune_uuid = commune_1.uuid if i < 8 else commune_2.uuid
                    
                    company = await DB.create_company(
                        conn=conn,
                        company_uuid=company_uuid,
                        user_uuid=user.uuid,
                        product_uuid=product_uuid,
                        commune_uuid=commune_uuid,
                        name=company_template["name"],
                        description_es=company_template["description_es"],
                        description_en=company_template["description_en"],
                        address=company_template["address"],
                        phone=company_template["phone"],
                        email=company_template["email"],
                        image_url=image_id,
                        image_extension=image_ext
                    )
                    
                    logger.info("company_created", 
                               company_uuid=str(company.uuid), 
                               company_name=company.name,
                               user_uuid=str(user.uuid))
                    
                except ValueError as e:
                    logger.warning("entity_already_exists", error=str(e), user_email=user_data["email"])
                    continue
                except Exception as e:
                    logger.error("error_processing_user", 
                                index=i+1, 
                                email=user_data["email"], 
                                error=str(e),
                                exc_info=True)
                    continue
            
            logger.info("creating_admin_user")
            try:
                admin = await DB.create_user(
                    conn=conn,
                    name="Admin User",
                    email="admin_test@mail.com",
                    password="password"
                )

                await conn.execute(
                    """
                    UPDATE proveo.users 
                    SET email_verified = TRUE,
                        verification_token = NULL,
                        verification_token_expires = NULL,
                        role = 'admin'
                    WHERE uuid = $1
                    """,
                    admin.uuid
                )
                logger.info("admin_user_created", admin_uuid=str(admin.uuid), email=admin.email)
                
            except ValueError:
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
                logger.info("admin_user_already_exists", message="Updated existing admin")
            
            logger.info("refreshing_search_index")
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search")
            logger.info("search_index_refreshed")
            
            logger.info("seed_complete", 
                       message="Test data seeding completed successfully",
                       users_count=len(TEST_USERS),
                       admin_created=True)
            
            print("\n✅ Seeding completed successfully!")
            print(f"Created {len(TEST_USERS)} test users with companies")
            print("Created 2 communes: Santiago Centro, Providencia")
            print("Created 2 products: Tecnología/Technology, Alimentos/Food")
            print("\nTest user credentials:")
            print("  Email: testuser01@proveo.com to testuser16@proveo.com")
            print("  Password: TestPass123!")
            print("\nAdmin credentials:")
            print("  Email: admin_test@mail.com")
            print("  Password: password")
            
        except Exception as e:
            logger.error("seed_failed", error=str(e), exc_info=True)
            raise
    
    logger.info("database_connection_closed")


if __name__ == "__main__":
    asyncio.run(seed_test_data())