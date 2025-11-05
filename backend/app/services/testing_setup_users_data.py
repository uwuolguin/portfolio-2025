"""
Seed test data: 16 users with companies
Usage: 
  python -m app.services.testing_setup_users_data
  docker compose exec backend python -m app.services.testing_setup_users_data
"""
import asyncio
import asyncpg
from app.config import settings
from app.auth.jwt import get_password_hash
from datetime import datetime, timezone
import uuid

TEST_USERS = [
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Test User 01",
        "email": "testuser01@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Test User 02",
        "email": "testuser02@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440003",
        "name": "Test User 03",
        "email": "testuser03@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440004",
        "name": "Test User 04",
        "email": "testuser04@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440005",
        "name": "Test User 05",
        "email": "testuser05@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440006",
        "name": "Test User 06",
        "email": "testuser06@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440007",
        "name": "Test User 07",
        "email": "testuser07@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440008",
        "name": "Test User 08",
        "email": "testuser08@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440009",
        "name": "Test User 09",
        "email": "testuser09@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440010",
        "name": "Test User 10",
        "email": "testuser10@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440011",
        "name": "Test User 11",
        "email": "testuser11@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440012",
        "name": "Test User 12",
        "email": "testuser12@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440013",
        "name": "Test User 13",
        "email": "testuser13@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440014",
        "name": "Test User 14",
        "email": "testuser14@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440015",
        "name": "Test User 15",
        "email": "testuser15@proveo.test",
        "password": "TestPass123!"
    },
    {
        "uuid": "550e8400-e29b-41d4-a716-446655440016",
        "name": "Test User 16",
        "email": "testuser16@proveo.test",
        "password": "TestPass123!"
    }
]

COMPANY_TEMPLATES = [
    {
        "name": "Tech Solutions SA",
        "description_es": "Soluciones tecnológicas innovadoras para empresas",
        "description_en": "Innovative technological solutions for businesses",
        "address": "Av. Providencia 1234, Providencia",
        "phone": "+56912345001",
        "email": "contact@techsolutions.cl"
    },
    {
        "name": "Green Foods Ltda",
        "description_es": "Alimentos orgánicos y sustentables de alta calidad",
        "description_en": "High quality organic and sustainable foods",
        "address": "Av. Apoquindo 5678, Las Condes",
        "phone": "+56912345002",
        "email": "info@greenfoods.cl"
    },
    {
        "name": "Build Master SpA",
        "description_es": "Construcción y remodelación de espacios residenciales",
        "description_en": "Construction and remodeling of residential spaces",
        "address": "Calle San Diego 9012, Santiago Centro",
        "phone": "+56912345003",
        "email": "contacto@buildmaster.cl"
    },
    {
        "name": "Express Logistics",
        "description_es": "Servicios de transporte y logística express",
        "description_en": "Express transport and logistics services",
        "address": "Av. Vicuña Mackenna 3456, Ñuñoa",
        "phone": "+56912345004",
        "email": "ops@expresslogistics.cl"
    },
    {
        "name": "Beauty & Care",
        "description_es": "Productos de belleza y cuidado personal premium",
        "description_en": "Premium beauty and personal care products",
        "address": "Av. Kennedy 7890, Vitacura",
        "phone": "+56912345005",
        "email": "ventas@beautycare.cl"
    },
    {
        "name": "Smart Home Systems",
        "description_es": "Automatización y domótica para hogares inteligentes",
        "description_en": "Home automation and smart home systems",
        "address": "Calle Huérfanos 1234, Santiago",
        "phone": "+56912345006",
        "email": "soporte@smarthome.cl"
    },
    {
        "name": "Café Artesanal",
        "description_es": "Café de especialidad tostado artesanalmente",
        "description_en": "Specialty coffee roasted by hand",
        "address": "Av. Italia 5678, Providencia",
        "phone": "+56912345007",
        "email": "hola@cafeartesanal.cl"
    },
    {
        "name": "Fitness Pro Center",
        "description_es": "Centro de entrenamiento y nutrición deportiva",
        "description_en": "Training center and sports nutrition",
        "address": "Av. Grecia 9012, Ñuñoa",
        "phone": "+56912345008",
        "email": "contacto@fitnesspro.cl"
    },
    {
        "name": "Digital Marketing Hub",
        "description_es": "Agencia de marketing digital y redes sociales",
        "description_en": "Digital marketing and social media agency",
        "address": "Av. Providencia 3456, Providencia",
        "phone": "+56912345009",
        "email": "info@digitalhub.cl"
    },
    {
        "name": "EcoClean Services",
        "description_es": "Servicios de limpieza ecológica y sustentable",
        "description_en": "Ecological and sustainable cleaning services",
        "address": "Calle Moneda 7890, Santiago Centro",
        "phone": "+56912345010",
        "email": "servicios@ecoclean.cl"
    },
    {
        "name": "Pet Care Clinic",
        "description_es": "Clínica veterinaria y cuidado integral de mascotas",
        "description_en": "Veterinary clinic and comprehensive pet care",
        "address": "Av. Macul 1234, Macul",
        "phone": "+56912345011",
        "email": "clinica@petcare.cl"
    },
    {
        "name": "Fashion Boutique",
        "description_es": "Ropa y accesorios de moda contemporánea",
        "description_en": "Contemporary fashion clothing and accessories",
        "address": "Av. Alonso de Córdova 5678, Vitacura",
        "phone": "+56912345012",
        "email": "tienda@fashionboutique.cl"
    },
    {
        "name": "Repair Workshop",
        "description_es": "Taller de reparación de electrodomésticos",
        "description_en": "Appliance repair workshop",
        "address": "Calle San Pablo 9012, Quinta Normal",
        "phone": "+56912345013",
        "email": "taller@repairworkshop.cl"
    },
    {
        "name": "Language Academy",
        "description_es": "Academia de idiomas con profesores nativos",
        "description_en": "Language academy with native teachers",
        "address": "Av. Apoquindo 3456, Las Condes",
        "phone": "+56912345014",
        "email": "info@languageacademy.cl"
    },
    {
        "name": "Garden Design Studio",
        "description_es": "Diseño y paisajismo de jardines residenciales",
        "description_en": "Residential garden design and landscaping",
        "address": "Av. La Dehesa 7890, Lo Barnechea",
        "phone": "+56912345015",
        "email": "proyectos@gardendesign.cl"
    },
    {
        "name": "Print & Graphics",
        "description_es": "Imprenta digital y servicios gráficos profesionales",
        "description_en": "Digital printing and professional graphic services",
        "address": "Calle Miraflores 1234, Santiago",
        "phone": "+56912345016",
        "email": "ventas@printgraphics.cl"
    }
]


async def seed_test_data():
    """Seed database with 16 test users and their companies"""
    
    print(" Starting test data seeding...\n")
    
    try:
        conn = await asyncpg.connect(settings.alembic_database_url)
        
        commune_uuid_1 = str(uuid.uuid4())
        commune_uuid_2 = str(uuid.uuid4())
        commune_insert_query = "INSERT INTO proveo.communes (name,uuid) VALUES ($1,$2) RETURNING uuid,name,created_at"
        commune_1 = await conn.fetchrow(commune_insert_query, "commune", commune_uuid_1)
        commune_2 = await conn.fetchrow(commune_insert_query, "commune2", commune_uuid_2)

        product_uuid_1 = str(uuid.uuid4())
        product_uuid_2 = str(uuid.uuid4())
        product_insert_query = "INSERT INTO proveo.products (uuid,name_es,name_en) VALUES ($1,$2,$3) RETURNING uuid,name_es,name_en,created_at"
        product_1 = await conn.fetchrow(product_insert_query, product_uuid_1, "producto", "product")
        product_2 = await conn.fetchrow(product_insert_query, product_uuid_2, "producto2", "product2")
        
        if not product_1 or not product_2 or not commune_1 or not commune_2:
            print("❌ Error: Database must have at least one product and one commune")
            print("   Please run migrations and add initial data first")
            return False
        
        
        created_users = 0
        created_companies = 0
        
        for i, user_data in enumerate(TEST_USERS):
            try:
                if i <6:
                    product_uuid=product_uuid_1
                    commune_uuid=commune_uuid_1
                else:
                    product_uuid=product_uuid_2
                    commune_uuid=commune_uuid_2

                # Check if user already exists
                existing = await conn.fetchval(
                    "SELECT uuid FROM proveo.users WHERE uuid = $1 OR email = $2",
                    user_data['uuid'], user_data['email']
                )
                
                if existing:
                    print(f"⏭️  User {i+1:02d} already exists: {user_data['email']}")
                    continue
                
                # Create user with verified email
                hashed_password = get_password_hash(user_data['password'])
                
                await conn.execute("""
                    INSERT INTO proveo.users 
                    (uuid, name, email, hashed_password, role, email_verified, 
                     verification_token, verification_token_expires)
                    VALUES ($1, $2, $3, $4, 'user', true, NULL, NULL)
                """, user_data['uuid'], user_data['name'], user_data['email'], hashed_password)
                
                created_users += 1
                print(f"✅ Created user {i+1:02d}: {user_data['email']}")
                
                # Create company for this user
                company_template = COMPANY_TEMPLATES[i]
                company_uuid = f"c50e8400-e29b-41d4-a716-44665544{i+1:04d}"
                
                # Image path follows the pattern: pictures/{user_uuid}.jpg
                image_url = f"pictures/{user_data['uuid']}.jpg"
                
                await conn.execute("""
                    INSERT INTO proveo.companies
                    (uuid, user_uuid, product_uuid, commune_uuid, name, 
                     description_es, description_en, address, phone, email, image_url)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, 
                    company_uuid, user_data['uuid'], product_uuid, commune_uuid,
                    company_template['name'], company_template['description_es'],
                    company_template['description_en'], company_template['address'],
                    company_template['phone'], company_template['email'], image_url
                )
                
                created_companies += 1
                print(f"   🏢 Created company: {company_template['name']}")
                print(f"   📸 Image path: {image_url}\n")
                
            except Exception as e:
                print(f"❌ Error creating user/company {i+1}: {e}\n")
                continue
        
        # Refresh materialized view
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search")
        print("🔄 Refreshed search index\n")
        
        #Create admin
        user_uuid = str(uuid.uuid4())
        hashed_password = get_password_hash("password")
                
        await conn.execute("""
                    INSERT INTO proveo.users 
                    (uuid, name, email, hashed_password, role, email_verified,verification_token,
                    verification_token_expires)
                    VALUES ($1, $2, $3, $4, 'admin', true,NULL,NULL)
                """, user_uuid, "admin_test","admin_test@mail.com", hashed_password)


        await conn.close()
        
        print("=" * 60)
        print(f"✅ Seeding complete!")
        print(f"   Users created: {created_users}/16")
        print(f"   Companies created: {created_companies}/16")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Fatal error during seeding: {e}")
        return False


def print_env_template():
    """Print template for .env file"""
    print("\n" + "=" * 60)
    print("📝 Add these credentials to your .env file:")
    print("=" * 60)
    print("\n# Test Users (all use password: TestPass123!)")
    
    for i, user in enumerate(TEST_USERS, 1):
        print(f"TEST_USER_{i:02d}_UUID={user['uuid']}")
        print(f"TEST_USER_{i:02d}_EMAIL={user['email']}")
        print(f"TEST_USER_{i:02d}_PASSWORD={user['password']}")
        print()
    
    print("=" * 60)
    print("📸 Image files to create:")
    print("=" * 60)
    print("\nPlace company images in: /files/pictures/")
    print("Required filenames (one per user):\n")
    
    for user in TEST_USERS:
        print(f"  • {user['uuid']}.jpg  (for {user['name']})")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("🚀 Proveo Test Data Seeder\n")
    
    # Print credentials template first
    print_env_template()
    
    print("\n" + "=" * 60)
    print("⚠️  WARNING: This will create 16 test users and companies")
    print("=" * 60)
    
    proceed = input("\nProceed with seeding? (yes/no): ").strip().lower()
    
    if proceed in ['yes', 'y']:
        success = asyncio.run(seed_test_data())
        
        if success:
            print("\n💡 Next steps:")
            print("   1. Add image files to /files/pictures/")
            print("   2. Restart the backend if needed")
            print("   3. Login with any test user email and password: TestPass123!")
        
        exit(0 if success else 1)
    else:
        print("\n❌ Seeding cancelled")
        exit(1)