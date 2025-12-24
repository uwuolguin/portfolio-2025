"""
Seed test data: 16 users with companies
Usage:
  python -m app.services.testing_setup_users_data
  docker compose exec backend python -m app.services.testing_setup_users_data
"""
import asyncio
import asyncpg
import httpx
from app.config import settings
from app.auth.jwt import get_password_hash
import uuid

TEST_USERS = [
    {"uuid":"550e8400-e29b-41d4-a716-446655440001","name":"Test User 01","email":"testuser01@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440002","name":"Test User 02","email":"testuser02@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440003","name":"Test User 03","email":"testuser03@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440004","name":"Test User 04","email":"testuser04@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440005","name":"Test User 05","email":"testuser05@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440006","name":"Test User 06","email":"testuser06@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440007","name":"Test User 07","email":"testuser07@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440008","name":"Test User 08","email":"testuser08@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440009","name":"Test User 09","email":"testuser09@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440010","name":"Test User 10","email":"testuser10@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440011","name":"Test User 11","email":"testuser11@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440012","name":"Test User 12","email":"testuser12@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440013","name":"Test User 13","email":"testuser13@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440014","name":"Test User 14","email":"testuser14@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440015","name":"Test User 15","email":"testuser15@proveo.com","password":"TestPass123!"},
    {"uuid":"550e8400-e29b-41d4-a716-446655440016","name":"Test User 16","email":"testuser16@proveo.com","password":"TestPass123!"},
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

async def fetch_test_image_bytes(image_name: str) -> bytes:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"http://nginx/files/test_pictures/{image_name}")
        r.raise_for_status()
        return r.content


async def upload_test_image_to_minio(company_uuid: str, user_uuid: str, image_index: int):
    image_bytes = await fetch_test_image_bytes(TEST_IMAGES[image_index % 3])
    files = {"file":(f"{company_uuid}.jpg",image_bytes,"image/jpeg")}
    data = {"company_id":company_uuid,"extension":".jpg","user_id":user_uuid}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{settings.image_service_url}/upload",files=files,data=data)
        r.raise_for_status()
        j = r.json()
        return j["image_id"], j["extension"]

async def seed_test_data():
    conn = await asyncpg.connect(settings.alembic_database_url)

    commune_uuid_1, commune_uuid_2 = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute("INSERT INTO proveo.communes (name,uuid) VALUES ($1,$2)","commune",commune_uuid_1)
    await conn.execute("INSERT INTO proveo.communes (name,uuid) VALUES ($1,$2)","commune2",commune_uuid_2)

    product_uuid_1, product_uuid_2 = str(uuid.uuid4()), str(uuid.uuid4())
    await conn.execute("INSERT INTO proveo.products (uuid,name_es,name_en) VALUES ($1,$2,$3)",product_uuid_1,"producto","product")
    await conn.execute("INSERT INTO proveo.products (uuid,name_es,name_en) VALUES ($1,$2,$3)",product_uuid_2,"producto2","product2")

    for i, user in enumerate(TEST_USERS):
        await conn.execute(
            "INSERT INTO proveo.users (uuid,name,email,hashed_password,role,email_verified) VALUES ($1,$2,$3,$4,'user',true)",
            user["uuid"],user["name"],user["email"],get_password_hash(user["password"])
        )

        company_uuid = f"c50e8400-e29b-41d4-a716-44665544{i+1:04d}"
        image_id, image_ext = await upload_test_image_to_minio(company_uuid,user["uuid"],i)
        company = COMPANY_TEMPLATES[i]

        await conn.execute(
            """
            INSERT INTO proveo.companies
            (uuid,user_uuid,product_uuid,commune_uuid,name,description_es,description_en,address,phone,email,image_url,image_extension)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            company_uuid,user["uuid"],
            product_uuid_1 if i < 8 else product_uuid_2,
            commune_uuid_1 if i < 8 else commune_uuid_2,
            company["name"],company["description_es"],company["description_en"],
            company["address"],company["phone"],company["email"],
            image_id,image_ext
        )

    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_test_data())
