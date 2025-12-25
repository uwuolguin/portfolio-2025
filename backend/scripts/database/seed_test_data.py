"""
Seed test data: 16 users with companies + 1 admin
Usage:
  python -m app.services.testing_setup_users_data
  docker compose exec backend python -m app.services.testing_setup_users_data
"""
import asyncio
import asyncpg
import httpx
from pathlib import Path
from io import BytesIO
from app.config import settings
from app.database.connection import get_db
from app.database.transactions import DB
from app.services.image_service_client import image_service_client
import structlog

logger = structlog.get_logger(__name__)

TEST_USERS = [
    {"name":"Test User 01","email":"testuser01@proveo.com","password":"TestPass123!"},
    {"name":"Test User 02","email":"testuser02@proveo.com","password":"TestPass123!"},
    {"name":"Test User 03","email":"testuser03@proveo.com","password":"TestPass123!"},
    {"name":"Test User 04","email":"testuser04@proveo.com","password":"TestPass123!"},
    {"name":"Test User 05","email":"testuser05@proveo.com","password":"TestPass123!"},
    {"name":"Test User 06","email":"testuser06@proveo.com","password":"TestPass123!"},
    {"name":"Test User 07","email":"testuser07@proveo.com","password":"TestPass123!"},
    {"name":"Test User 08","email":"testuser08@proveo.com","password":"TestPass123!"},
    {"name":"Test User 09","email":"testuser09@proveo.com","password":"TestPass123!"},
    {"name":"Test User 10","email":"testuser10@proveo.com","password":"TestPass123!"},
    {"name":"Test User 11","email":"testuser11@proveo.com","password":"TestPass123!"},
    {"name":"Test User 12","email":"testuser12@proveo.com","password":"TestPass123!"},
    {"name":"Test User 13","email":"testuser13@proveo.com","password":"TestPass123!"},
    {"name":"Test User 14","email":"testuser14@proveo.com","password":"TestPass123!"},
    {"name":"Test User 15","email":"testuser15@proveo.com","password":"TestPass123!"},
    {"name":"Test User 16","email":"testuser16@proveo.com","password":"TestPass123!"},
]

COMPANY_TEMPLATES = [
    {"name":"Tech Solutions SA","description_es":"Soluciones tecnológicas innovadoras para empresas","description_en":"Innovative technological solutions for businesses","address":"Av. Providencia 1234, Providencia","phone":"+56912345001","email":"contact@techsolutions.cl"},
    {"name":"Green Foods Ltda","description_es":"Alimentos orgánicos y sustentables de alta calidad","description_en":"High quality organic and sustainable foods","address":"Av. Apoquindo 5678, Las Condes","phone":"+56912345002","email":"info@greenfoods.cl"},
    {"name":"Build Master SpA","description_es":"Construcción y remodelación de espacios residenciales","description_en":"Construction and remodeling of residential spaces","address":"Calle San Diego 9012, Santiago Centro","phone":"+56912345003","email":"contacto@buildmaster.cl"},
    {"name":"Express Logistics","description_es":"Servicios de transporte y logística express","description_en":"Express transport and logistics services","address":"Av. Vicuña Mackenna 3456, Ñuñoa","phone":"+56912345004","email":"ops@expresslogistics.cl"},
    {"name":"Beauty & Care","description_es":"Productos de belleza y cuidado personal premium","description_en":"Premium beauty and personal care products","address":"Av. Kennedy 7890, Vitacura","phone":"+56912345005","email":"ventas@beautycare.cl"},
    {"name":"Smart Home Systems","description_es":"Automatización y domótica para hogares inteligentes","description_en":"Home automation and smart home systems","address":"Calle Huérfanos 1234, Santiago","phone":"+56912345006","email":"soporte@smarthome.cl"},
    {"name":"Café Artesanal","description_es":"Café de especialidad tostado artesanalmente","description_en":"Specialty coffee roasted by hand","address":"Av. Italia 5678, Providencia","phone":"+56912345007","email":"hola@cafeartesanal.cl"},
    {"name":"Fitness Pro Center","description_es":"Centro de entrenamiento y nutrición deportiva","description_en":"Training center and sports nutrition","address":"Av. Grecia 9012, Ñuñoa","phone":"+56912345008","email":"contacto@fitnesspro.cl"},
    {"name":"Digital Marketing Hub","description_es":"Agencia de marketing digital y redes sociales","description_en":"Digital marketing and social media agency","address":"Av. Providencia 3456, Providencia","phone":"+56912345009","email":"info@digitalhub.cl"},
    {"name":"EcoClean Services","description_es":"Servicios de limpieza ecológica y sustentable","description_en":"Ecological and sustainable cleaning services","address":"Calle Moneda 7890, Santiago Centro","phone":"+56912345010","email":"servicios@ecoclean.cl"},
    {"name":"Pet Care Clinic","description_es":"Clínica veterinaria y cuidado integral de mascotas","description_en":"Veterinary clinic and comprehensive pet care","address":"Av. Macul 1234, Macul","phone":"+56912345011","email":"clinica@petcare.cl"},
    {"name":"Fashion Boutique","description_es":"Ropa y accesorios de moda contemporánea","description_en":"Contemporary fashion clothing and accessories","address":"Av. Alonso de Córdova 5678, Vitacura","phone":"+56912345012","email":"tienda@fashionboutique.cl"},
    {"name":"Repair Workshop","description_es":"Taller de reparación de electrodomésticos","description_en":"Appliance repair workshop","address":"Calle San Pablo 9012, Quinta Normal","phone":"+56912345013","email":"taller@repairworkshop.cl"},
    {"name":"Language Academy","description_es":"Academia de idiomas con profesores nativos","description_en":"Language academy with native teachers","address":"Av. Apoquindo 3456, Las Condes","phone":"+56912345014","email":"info@languageacademy.cl"},
    {"name":"Garden Design Studio","description_es":"Diseño y paisajismo de jardines residenciales","description_en":"Residential garden design and landscaping","address":"Av. La Dehesa 7890, Lo Barnechea","phone":"+56912345015","email":"proyectos@gardendesign.cl"},
    {"name":"Print & Graphics","description_es":"Imprenta digital y servicios gráficos profesionales","description_en":"Digital printing and professional graphic services","address":"Calle Miraflores 1234, Santiago","phone":"+56912345016","email":"ventas@printgraphics.cl"},
]

TEST_IMAGES = ["test1.jpg","test2.jpg","test3.jpg"]


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
    conn = await asyncpg.connect(settings.alembic_database_url)
    
    try:
        logger.info("seed_start", message="Starting test data seeding")
        
        # Create communes using DB.create_commune
        logger.info("creating_communes")
        commune_1 = await DB.create_commune(conn, "Santiago Centro")
        commune_2 = await DB.create_commune(conn, "Providencia")
        logger.info("communes_created", commune_1=commune_1.name, commune_2=commune_2.name)
        
        # Create products using DB.create_product
        logger.info("creating_products")
        product_1 = await DB.create_product(conn, "Tecnología", "Technology")
        product_2 = await DB.create_product(conn, "Alimentos", "Food")
        logger.info("products_created", product_1_es=product_1.name_es, product_2_es=product_2.name_es)
        
        # Create users and companies
        for i, user_data in enumerate(TEST_USERS):
            logger.info("processing_user", index=i+1, email=user_data["email"])
            
            try:
                # Create user using DB.create_user
                user = await DB.create_user(
                    conn=conn,
                    name=user_data["name"],
                    email=user_data["email"],
                    password=user_data["password"]
                )
                
                # Mark email as verified for test users
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
                
                # Upload image to image service
                company_template = COMPANY_TEMPLATES[i]
                image_index = i % len(TEST_IMAGES)
                test_image_name = TEST_IMAGES[image_index]
                
                logger.info("uploading_image", image=test_image_name, user_uuid=str(user.uuid))
                image_stream = await fetch_test_image_bytes(test_image_name)
                
                # Generate company UUID
                import uuid
                company_uuid = uuid.uuid4()
                
                # Upload image using image_service_client
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
                
                # Create company using DB.create_company
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
                # User or company already exists
                logger.warning("entity_already_exists", error=str(e), user_email=user_data["email"])
                continue
            except Exception as e:
                logger.error("error_processing_user", 
                            index=i+1, 
                            email=user_data["email"], 
                            error=str(e),
                            exc_info=True)
                continue
        
        # Create admin user if doesn't exist
        logger.info("creating_admin_user")
        try:
            admin = await DB.create_user(
                conn=conn,
                name="Admin User",
                email="admin_test@mail.com",
                password="password"
            )
            
            # Mark admin as verified and set admin role
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
            
        except ValueError as e:
            # Admin already exists, just update role
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
        
        # Refresh materialized view for search
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
    finally:
        await conn.close()
        logger.info("database_connection_closed")


if __name__ == "__main__":
    asyncio.run(seed_test_data())