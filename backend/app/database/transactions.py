import asyncpg
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List, Dict, Any
from enum import Enum
from uuid import UUID
from app.database.db_retry import db_retry
from app.auth.jwt import get_password_hash
from app.config import settings
import uuid
from app.auth.csrf import generate_csrf_token
from datetime import datetime, timedelta, timezone
from app.services.image_service_client import image_service_client
import asyncio

logger = structlog.get_logger(__name__)

class IsolationLevel(Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"

@asynccontextmanager
async def transaction(
    conn: asyncpg.Connection,
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    readonly: bool = False
) -> AsyncGenerator[asyncpg.Connection, None]:
    options = [f"ISOLATION LEVEL {isolation.value}"]
    if readonly:
        options.append("READ ONLY")
    tx_sql = f"BEGIN {' '.join(options)}"
    try:
        await conn.execute(tx_sql)
        logger.debug("transaction_started", isolation=isolation.value, readonly=readonly)
        yield conn
        await conn.execute("COMMIT")
        logger.debug("transaction_committed")
    except Exception as e:
        await conn.execute("ROLLBACK")
        logger.warning("transaction_rolled_back", error=str(e), error_type=type(e).__name__)
        raise

class DB:

    @staticmethod
    @db_retry()
    async def create_user(conn: asyncpg.Connection, name: str, email: str, password: str) -> Dict[str, Any]:
        async with transaction(conn):
            hashed_password = get_password_hash(password)
            user_uuid = str(uuid.uuid4())
            
            verification_token = generate_csrf_token()
            token_expires = datetime.now(timezone.utc) + timedelta(hours=settings.verification_token_email_time)
            
            query = """
                INSERT INTO proveo.users 
                    (uuid, name, email, hashed_password, role, verification_token, verification_token_expires)
                VALUES ($1, $2, $3, $4, 'user', $5, $6)
                ON CONFLICT (email) DO NOTHING
                RETURNING uuid, name, email, role, email_verified, verification_token, created_at
            """
            row = await conn.fetchrow(
                query, user_uuid, name, email, hashed_password, 
                verification_token, token_expires
            )
            
            if row is None:
                raise ValueError(f"Email {email} is already registered")
            
            logger.info("user_created_pending_verification", 
                       user_uuid=str(row["uuid"]), 
                       email=email)
            return dict(row)
        
    @staticmethod
    @db_retry()
    async def get_user_by_email(conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
        async with transaction(conn, readonly=True):
            query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at 
                FROM proveo.users 
                WHERE email = $1
            """
            row = await conn.fetchrow(query, email)
            return dict(row) if row else None
    
    @staticmethod
    @db_retry()
    async def verify_email(conn: asyncpg.Connection, token: str) -> Dict[str, Any]:
        async with transaction(conn):
            query = """
                SELECT uuid, name, email, verification_token_expires
                FROM proveo.users
                WHERE verification_token = $1 AND email_verified = FALSE
            """
            user = await conn.fetchrow(query, token)
            
            if not user:
                raise ValueError("Invalid or expired verification token")
            
            if user['verification_token_expires'] < datetime.now(timezone.utc):
                raise ValueError("Verification token has expired")
            
            update_query = """
                UPDATE proveo.users
                SET email_verified = TRUE,
                    verification_token = NULL,
                    verification_token_expires = NULL
                WHERE uuid = $1
                RETURNING uuid, name, email, role, email_verified
            """
            verified_user = await conn.fetchrow(update_query, user['uuid'])
            
            logger.info("email_verified", user_uuid=str(user['uuid']), email=user['email'])
            return dict(verified_user)
        
    @staticmethod
    @db_retry()
    async def resend_verification_email(conn: asyncpg.Connection, email: str) -> Dict[str, Any]:
        async with transaction(conn):
            query = """
                SELECT uuid, name, email, email_verified
                FROM proveo.users
                WHERE email = $1
            """
            user = await conn.fetchrow(query, email)
            
            if not user:
                raise ValueError("User not found")
            
            if user['email_verified']:
                raise ValueError("Email already verified")
            
            verification_token = generate_csrf_token()
            token_expires = datetime.now(timezone.utc) + timedelta(hours=settings.verification_token_email_time)
            
            update_query = """
                UPDATE proveo.users
                SET verification_token = $1,
                    verification_token_expires = $2
                WHERE uuid = $3
                RETURNING uuid, name, email, verification_token
            """
            updated_user = await conn.fetchrow(
                update_query, verification_token, token_expires, user['uuid']
            )
            
            logger.info("verification_token_regenerated", 
                       user_uuid=str(user['uuid']), 
                       email=email)
            return dict(updated_user)
    
    @staticmethod
    @db_retry()
    async def delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID) -> Dict[str, Any]:
        deleted_image: str | None = None
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED):
            user_query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at
                FROM proveo.users
                WHERE uuid = $1
            """
            user = await conn.fetchrow(user_query, user_uuid)
            if not user:
                raise ValueError(f"User with UUID {user_uuid} not found")

            company_query = """
                SELECT uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                    description_en, address, phone, email, image_url, image_extension,
                    created_at, updated_at
                FROM proveo.companies
                WHERE user_uuid = $1
            """
            company = await conn.fetchrow(company_query, user_uuid)

            if company:
                image_id = company.get("image_url")
                image_ext = company.get("image_extension")
                if image_id and image_ext:
                    deleted_image = f"{image_id}{image_ext}"
                    company_uuid = str(company["uuid"])

                insert_deleted_company = """
                    INSERT INTO proveo.companies_deleted
                        (uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                        description_en, address, phone, email, image_url, image_extension,
                        created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """
                await conn.execute(
                    insert_deleted_company,
                    company["uuid"], company["user_uuid"], company["product_uuid"],
                    company["commune_uuid"], company["name"], company["description_es"],
                    company["description_en"], company["address"], company["phone"],
                    company["email"], company["image_url"], company["image_extension"],
                    company["created_at"], company["updated_at"]
                )

                await conn.execute("DELETE FROM proveo.companies WHERE uuid = $1", company["uuid"])

                logger.info(
                    "user_company_deleted",
                    user_uuid=str(user_uuid),
                    company_uuid=str(company["uuid"])
                )

            insert_deleted_user = """
                INSERT INTO proveo.users_deleted
                    (uuid, name, email, hashed_password, role, email_verified, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """
            await conn.execute(
                insert_deleted_user,
                user["uuid"], user["name"], user["email"], user["hashed_password"],
                user["role"], user["email_verified"], user["created_at"]
            )

            await conn.execute("DELETE FROM proveo.users WHERE uuid = $1", user_uuid)

            logger.info(
                "user_deleted_with_cascade",
                user_uuid=str(user_uuid),
                email=user["email"],
                company_deleted=1 if company else 0
            )

        if deleted_image:
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(deleted_image),
                    timeout=15.0
                )
                if success:
                    logger.info(
                        "user_self_delete_image_removed",
                        company_uuid=company_uuid,
                        image_path=deleted_image
                    )
                else:
                    logger.warning(
                        "user_self_delete_image_not_found",
                        company_uuid=company_uuid,
                        image_path=deleted_image
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "user_self_delete_image_timeout",
                    company_uuid=company_uuid,
                    image_path=deleted_image,
                    message="Image deletion timed out after 15s - will be cleaned by cronjob"
                )
            except Exception as e:
                logger.error(
                    "user_self_delete_image_error",
                    company_uuid=company_uuid,
                    image_path=deleted_image,
                    error=str(e)
                )

        return {
            "user_uuid": str(user_uuid),
            "email": user["email"],
            "company_deleted": 1 if company else 0,
            "image_deleted": 1 if deleted_image else 0
        }

        
    @staticmethod
    @db_retry()
    async def get_all_users_admin(conn: asyncpg.Connection, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = """
            SELECT u.uuid, u.name, u.email, u.created_at
            FROM proveo.users u
            ORDER BY u.created_at DESC
            LIMIT $1 OFFSET $2
        """
        rows = await conn.fetch(query, limit, offset)
        return [dict(row) for row in rows]

    
    @staticmethod
    @db_retry()
    async def admin_delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID, admin_email: str) -> Dict[str, Any]:
        deleted_images: list[str] = []
        images_to_delete: list[tuple[str, str, str]] = []

        # Verify admin permissions before transaction
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            admin_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete other users.")
        
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED):
            user_query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at
                FROM proveo.users WHERE uuid=$1
            """
            user = await conn.fetchrow(user_query, user_uuid)
            if not user:
                raise ValueError(f"User with UUID {user_uuid} not found")
            
            companies_query = """
                SELECT uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                    description_en, address, phone, email, image_url, image_extension,
                    created_at, updated_at
                FROM proveo.companies WHERE user_uuid=$1
            """
            companies = await conn.fetch(companies_query, user_uuid)
            
            if companies:
                # Collect images for deletion after transaction
                for company in companies:
                    image_id = company.get("image_url")
                    image_ext = company.get("image_extension")
                    if image_id and image_ext:
                        images_to_delete.append((image_id, image_ext, str(company["uuid"])))
                
                # Batch insert deleted companies
                delete_companies_query = """
                    INSERT INTO proveo.companies_deleted
                        (uuid, user_uuid, product_uuid, commune_uuid, name, description_es, 
                        description_en, address, phone, email, image_url, image_extension,
                        created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """
                company_data = [
                    (
                        company["uuid"], company["user_uuid"], company["product_uuid"],
                        company["commune_uuid"], company["name"], company["description_es"],
                        company["description_en"], company["address"], company["phone"],
                        company["email"], company["image_url"], company["image_extension"],
                        company["created_at"], company["updated_at"]
                    )
                    for company in companies
                ]
                await conn.executemany(delete_companies_query, company_data)
                
                await conn.execute("DELETE FROM proveo.companies WHERE user_uuid=$1", user_uuid)
                
                logger.info(
                    "admin_deleted_user_companies", 
                    user_uuid=str(user_uuid), 
                    companies_count=len(companies),
                    admin_email=admin_email
                )
            
            insert_deleted_user = """
                INSERT INTO proveo.users_deleted 
                    (uuid, name, email, hashed_password, role, email_verified, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await conn.execute(insert_deleted_user, 
                user["uuid"], user["name"], user["email"], user["hashed_password"],
                user["role"], user["email_verified"], user["created_at"]
            )
            
            await conn.execute("DELETE FROM proveo.users WHERE uuid=$1", user_uuid)
            
            logger.info(
                "admin_deleted_user_with_cascade", 
                deleted_user_uuid=str(user_uuid), 
                deleted_user_email=user["email"], 
                companies_deleted=len(companies), 
                admin_email=admin_email
            )


        if images_to_delete:
            for image_id, image_ext, company_uuid in images_to_delete:
                image_path = f"{image_id}{image_ext}"
                try:
                    success = await asyncio.wait_for(
                        image_service_client.delete_image(image_path),
                        timeout=15.0
                    )
                    if success:
                        deleted_images.append(image_path)
                        logger.info(
                            "admin_delete_user_image_removed",
                            company_uuid=company_uuid,
                            image_path=image_path,
                            admin_email=admin_email
                        )
                    else:
                        logger.warning(
                            "admin_delete_user_image_not_found",
                            company_uuid=company_uuid,
                            image_path=image_path,
                            admin_email=admin_email
                        )
                except asyncio.TimeoutError:
                    logger.warning(
                        "admin_delete_user_image_timeout",
                        company_uuid=company_uuid,
                        image_path=image_path,
                        admin_email=admin_email,
                        message="Image deletion timed out after 15s - will be cleaned by cronjob"
                    )
                except Exception as e:
                    logger.error(
                        "admin_delete_user_image_error",
                        company_uuid=company_uuid,
                        image_path=image_path,
                        error=str(e),
                        admin_email=admin_email
                    )

        
        return {
            "user_uuid": str(user_uuid), 
            "email": user["email"], 
            "companies_deleted": len(companies),
            "images_deleted": len(deleted_images)
        }
        
    @staticmethod
    @db_retry()
    async def get_all_products(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        query = "SELECT uuid, name_es, name_en, created_at FROM proveo.products ORDER BY name_en ASC"
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    @db_retry()
    async def create_product(conn: asyncpg.Connection, name_es: str, name_en: str, user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can create products.")
        
        async with transaction(conn):
            # Use ON CONFLICT to prevent race condition
            product_uuid = str(uuid.uuid4())
            insert_query = """
                INSERT INTO proveo.products (uuid,name_es,name_en) 
                VALUES ($1,$2,$3) 
                ON CONFLICT (name_es) DO NOTHING
                RETURNING uuid,name_es,name_en,created_at
            """
            row = await conn.fetchrow(insert_query, product_uuid, name_es, name_en)
            
            if row is None:
                raise ValueError("Product with this name already exists")
            
            logger.info("product_created", product_uuid=str(row["uuid"]))
            return dict(row)

    @staticmethod
    @db_retry()
    async def update_product_by_uuid(conn: asyncpg.Connection, product_uuid: UUID, name_es: Optional[str], name_en: Optional[str], user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can update products.")
        
        async with transaction(conn):
            existing = await conn.fetchval("SELECT 1 FROM proveo.products WHERE uuid=$1", product_uuid)
            if not existing:
                raise ValueError(f"Product with UUID {product_uuid} not found")
            
            update_fields = []
            params = []
            param_count = 1
            
            if name_es is not None:
                update_fields.append(f"name_es=${param_count}")
                params.append(name_es)
                param_count += 1
            if name_en is not None:
                update_fields.append(f"name_en=${param_count}")
                params.append(name_en)
                param_count += 1
            
            if not update_fields:
                raise ValueError("No fields provided for update")
            
            params.append(product_uuid)
            update_query = f"UPDATE proveo.products SET {', '.join(update_fields)} WHERE uuid=${param_count} RETURNING uuid,name_es,name_en,created_at"
            row = await conn.fetchrow(update_query, *params)
            
            logger.info("product_updated", product_uuid=str(product_uuid))
            return dict(row)
        
    @staticmethod
    @db_retry()
    async def delete_product_by_uuid(conn: asyncpg.Connection, product_uuid: UUID, user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete products.")
        
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED):
            product_query = "SELECT uuid,name_es,name_en,created_at FROM proveo.products WHERE uuid=$1"
            product = await conn.fetchrow(product_query, product_uuid)
            if not product:
                raise ValueError(f"Product with UUID {product_uuid} not found")
            
            company_count = await conn.fetchval("SELECT COUNT(*) FROM proveo.companies WHERE product_uuid=$1", product_uuid)
            if company_count > 0:
                raise ValueError(f"Cannot delete product '{product['name_en']}'. {company_count} company(ies) are still using this product.")
            
            insert_deleted = "INSERT INTO proveo.products_deleted (uuid,name_es,name_en,created_at) VALUES ($1,$2,$3,$4)"
            await conn.execute(insert_deleted, product["uuid"], product["name_es"], product["name_en"], product["created_at"])
            
            await conn.execute("DELETE FROM proveo.products WHERE uuid=$1", product_uuid)
            
            logger.info("product_deleted", product_uuid=str(product_uuid))
            return {"uuid": str(product["uuid"]), "name_es": product["name_es"], "name_en": product["name_en"]}

    @staticmethod
    @db_retry()
    async def get_all_communes(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        query = "SELECT uuid,name,created_at FROM proveo.communes ORDER BY name ASC"
        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    @staticmethod
    @db_retry()
    async def create_commune(conn: asyncpg.Connection, name: str, user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can create communes.")
        
        async with transaction(conn):
            commune_uuid = str(uuid.uuid4())
            insert_query = """
                INSERT INTO proveo.communes (name,uuid) 
                VALUES ($1,$2) 
                ON CONFLICT (name) DO NOTHING
                RETURNING uuid,name,created_at
            """
            row = await conn.fetchrow(insert_query, name, commune_uuid)
            
            if row is None:
                raise ValueError("Commune with this name already exists")
            
            logger.info("commune_created", uuid=commune_uuid)
            return dict(row)

    @staticmethod
    @db_retry()
    async def update_commune_by_uuid(conn: asyncpg.Connection, commune_uuid: UUID, name: Optional[str], user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can update communes.")
        
        async with transaction(conn):
            existing = await conn.fetchval("SELECT 1 FROM proveo.communes WHERE uuid=$1", commune_uuid)
            if not existing:
                raise ValueError(f"Commune with UUID {commune_uuid} not found")
            
            if name is None:
                raise ValueError("Name is required for update")
            
            update_query = "UPDATE proveo.communes SET name=$1 WHERE uuid=$2 RETURNING uuid,name,created_at"
            row = await conn.fetchrow(update_query, name, commune_uuid)
            
            logger.info("commune_updated", commune_uuid=str(commune_uuid))
            return dict(row)

    @staticmethod
    @db_retry()
    async def delete_commune_by_uuid(conn: asyncpg.Connection, commune_uuid: UUID, user_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            user_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete communes.")
        
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED):
            commune_query = "SELECT uuid,name,created_at FROM proveo.communes WHERE uuid=$1"
            commune = await conn.fetchrow(commune_query, commune_uuid)
            if not commune:
                raise ValueError(f"Commune with UUID {commune_uuid} not found")
            
            company_count = await conn.fetchval("SELECT COUNT(*) FROM proveo.companies WHERE commune_uuid=$1", commune_uuid)
            if company_count > 0:
                raise ValueError(f"Cannot delete commune '{commune['name']}'. {company_count} company(ies) are still located in this commune.")
            
            insert_deleted = "INSERT INTO proveo.communes_deleted (uuid,name,created_at) VALUES ($1,$2,$3)"
            await conn.execute(insert_deleted, commune["uuid"], commune["name"], commune["created_at"])
            
            await conn.execute("DELETE FROM proveo.communes WHERE uuid=$1", commune_uuid)
            
            logger.info("commune_deleted", commune_uuid=str(commune_uuid))
            return {"uuid": str(commune["uuid"]), "name": commune["name"]}

    @staticmethod
    @db_retry()
    async def get_company_by_uuid(conn: asyncpg.Connection, company_uuid: UUID) -> Optional[Dict[str, Any]]:
        query = """
            SELECT c.uuid,c.user_uuid,c.product_uuid,c.commune_uuid,c.name,c.description_es,c.description_en,
                   c.address,c.phone,c.email,c.image_url,c.image_extension,c.created_at,c.updated_at,
                   u.name as user_name,u.email as user_email,
                   p.name_es as product_name_es,p.name_en as product_name_en,
                   cm.name as commune_name
            FROM proveo.companies c
            LEFT JOIN proveo.users u ON u.uuid=c.user_uuid
            LEFT JOIN proveo.products p ON p.uuid=c.product_uuid
            LEFT JOIN proveo.communes cm ON cm.uuid=c.commune_uuid
            WHERE c.uuid=$1
        """
        row = await conn.fetchrow(query, company_uuid)
        return dict(row) if row else None

    @staticmethod
    @db_retry()
    async def get_all_companies(conn: asyncpg.Connection, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        query = """
            SELECT c.uuid,c.user_uuid,c.product_uuid,c.commune_uuid,c.name,c.description_es,c.description_en,
                   c.address,c.phone,c.email,c.image_url,c.image_extension,c.created_at,c.updated_at,
                   u.name as user_name,u.email as user_email,
                   p.name_es as product_name_es,p.name_en as product_name_en,
                   cm.name as commune_name
            FROM proveo.companies c
            LEFT JOIN proveo.users u ON u.uuid=c.user_uuid
            LEFT JOIN proveo.products p ON p.uuid=c.product_uuid
            LEFT JOIN proveo.communes cm ON cm.uuid=c.commune_uuid
            ORDER BY c.created_at DESC
            LIMIT $1 OFFSET $2
        """
        rows = await conn.fetch(query, limit, offset)
        return [dict(row) for row in rows]

    @staticmethod
    @db_retry()
    async def get_companies_by_user_uuid(conn: asyncpg.Connection, user_uuid: UUID) -> List[Dict[str, Any]]:
        query = """
            SELECT c.uuid,c.user_uuid,c.product_uuid,c.commune_uuid,c.name,c.description_es,c.description_en,
                   c.address,c.phone,c.email,c.image_url,c.image_extension,c.created_at,c.updated_at,
                   u.name as user_name,u.email as user_email,
                   p.name_es as product_name_es,p.name_en as product_name_en,
                   cm.name as commune_name
            FROM proveo.companies c
            LEFT JOIN proveo.users u ON u.uuid=c.user_uuid
            LEFT JOIN proveo.products p ON p.uuid=c.product_uuid
            LEFT JOIN proveo.communes cm ON cm.uuid=c.commune_uuid
            WHERE c.user_uuid=$1
            ORDER BY c.created_at DESC
        """
        rows = await conn.fetch(query, user_uuid)
        return [dict(row) for row in rows]

    @staticmethod
    @db_retry()
    async def create_company(
        conn: asyncpg.Connection,
        user_uuid: UUID,
        product_uuid: UUID,
        commune_uuid: UUID,
        name: str,                      
        description_es: str,            
        description_en: str,            
        address: str,                   
        phone: str,                     
        email: str,                     
        image_url: str,                 
        image_extension: str,           
        company_uuid: str               
    ) -> Dict[str, Any]:
        async with transaction(conn):
            existing_company = await conn.fetchval(
                "SELECT 1 FROM proveo.companies WHERE user_uuid=$1",
                user_uuid
            )
            if existing_company:
                raise ValueError("Each user can only create one company. Please update your existing company.")
            
            product_exists = await conn.fetchval("SELECT 1 FROM proveo.products WHERE uuid=$1", product_uuid)
            if not product_exists:
                raise ValueError(f"Product with UUID {product_uuid} does not exist")
            
            commune_exists = await conn.fetchval("SELECT 1 FROM proveo.communes WHERE uuid=$1", commune_uuid)
            if not commune_exists:
                raise ValueError(f"Commune with UUID {commune_uuid} does not exist")
            
            insert_query = """
                INSERT INTO proveo.companies
                    (user_uuid, product_uuid, commune_uuid, name, description_es, description_en,
                    address, phone, email, image_url, image_extension, uuid)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                RETURNING uuid """
            row = await conn.fetchrow(
                insert_query, 
                user_uuid, 
                product_uuid, 
                commune_uuid, 
                name,
                description_es, 
                description_en, 
                address, 
                phone, 
                email, 
                image_url,
                image_extension,
                company_uuid 
            )

            logger.info("company_created", company_uuid=str(row["uuid"]), user_uuid=str(user_uuid))
    
            return await DB.get_company_by_uuid(conn, row["uuid"])
        
    @staticmethod
    @db_retry()
    async def update_company_by_uuid(
        conn: asyncpg.Connection,
        company_uuid: UUID,
        user_uuid: UUID,
        name: Optional[str] = None,
        description_es: Optional[str] = None,
        description_en: Optional[str] = None,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        image_extension: Optional[str] = None,
        image_url: Optional[str] = None,
        product_uuid: Optional[UUID] = None,
        commune_uuid: Optional[UUID] = None
    ) -> Dict[str, Any]:
        async with transaction(conn):
            owner_check = await conn.fetchval("SELECT user_uuid FROM proveo.companies WHERE uuid=$1", company_uuid)
            if not owner_check:
                raise ValueError(f"Company with UUID {company_uuid} not found")
            if owner_check != user_uuid:
                raise PermissionError("You can only update your own companies")
            
            update_fields = []
            params = []
            param_count = 1
            
            for field, value in [
                ("name", name), ("description_es", description_es), ("description_en", description_en),
                ("address", address), ("phone", phone), ("email", email), ("image_url", image_url),
                ("image_extension", image_extension)
            ]:
                if value is not None:
                    update_fields.append(f"{field}=${param_count}")
                    params.append(value)
                    param_count += 1
            
            if product_uuid is not None:
                product_exists = await conn.fetchval("SELECT 1 FROM proveo.products WHERE uuid=$1", product_uuid)
                if not product_exists:
                    raise ValueError(f"Product with UUID {product_uuid} does not exist")
                update_fields.append(f"product_uuid=${param_count}")
                params.append(product_uuid)
                param_count += 1
            
            if commune_uuid is not None:
                commune_exists = await conn.fetchval("SELECT 1 FROM proveo.communes WHERE uuid=$1", commune_uuid)
                if not commune_exists:
                    raise ValueError(f"Commune with UUID {commune_uuid} does not exist")
                update_fields.append(f"commune_uuid=${param_count}")
                params.append(commune_uuid)
                param_count += 1
            
            if not update_fields:
                raise ValueError("No fields provided for update")
            
            update_fields.append("updated_at=NOW()")
            params.append(company_uuid)
            update_query = f"UPDATE proveo.companies SET {', '.join(update_fields)} WHERE uuid=${param_count} RETURNING uuid"
            await conn.execute(update_query, *params)
            
            logger.info("company_updated", company_uuid=str(company_uuid), user_uuid=str(user_uuid))
            return await DB.get_company_by_uuid(conn, company_uuid)

    @staticmethod
    @db_retry()
    async def delete_company_by_uuid(conn: asyncpg.Connection, company_uuid: UUID, user_uuid: UUID) -> bool:
        async with transaction(conn):
            company_query = "SELECT * FROM proveo.companies WHERE uuid=$1 AND user_uuid=$2"
            company = await conn.fetchrow(company_query, company_uuid, user_uuid)
            if not company:
                return False

            insert_deleted = """
                INSERT INTO proveo.companies_deleted
                    (uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                    description_en, address, phone, email, image_url, image_extension, 
                    created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            """
            await conn.execute(insert_deleted, 
                company["uuid"], company["user_uuid"], company["product_uuid"],
                company["commune_uuid"], company["name"], company["description_es"],
                company["description_en"], company["address"], company["phone"],
                company["email"], company["image_url"], company["image_extension"],
                company["created_at"], company["updated_at"]
            )

            await conn.execute("DELETE FROM proveo.companies WHERE uuid=$1", company_uuid)
            logger.info("company_deleted", company_uuid=str(company_uuid))


        image_id = company.get("image_url")
        image_ext = company.get("image_extension")
        if image_id and image_ext:
            image_path = f"{image_id}{image_ext}"
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(image_path),
                    timeout=15.0
                )
                if success:
                    logger.info(
                        "company_image_deleted",
                        company_uuid=str(company_uuid),
                        image_path=image_path
                    )
                else:
                    logger.warning(
                        "company_image_not_found",
                        company_uuid=str(company_uuid),
                        image_path=image_path
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "company_image_delete_timeout",
                    company_uuid=str(company_uuid),
                    image_path=image_path
                )
            except Exception as e:
                logger.error(
                    "company_image_delete_error",
                    company_uuid=str(company_uuid),
                    image_path=image_path,
                    error=str(e)
                )

        return True


    @staticmethod
    @db_retry()
    async def search_companies(
        conn: asyncpg.Connection,
        query: str,
        lang: str = "es",
        commune: Optional[str] = None,
        product: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        from typing import Any
        
        search = (query or "").strip().lower()
        params: List[Any] = []
        
        if not search:
            base_query = """
                SELECT company_id, company_name, company_description_es, company_description_en,
                    address, company_email, product_name_es, product_name_en,
                    phone, image_url, user_name, user_email, commune_name
                FROM proveo.company_search
                WHERE 1=1
            """
            order_clause = " ORDER BY company_name ASC"
        elif len(search) < 4:
            base_query = """
                SELECT company_id, company_name, company_description_es, company_description_en,
                    address, company_email, product_name_es, product_name_en,
                    phone, image_url, user_name, user_email, commune_name
                FROM proveo.company_search
                WHERE searchable_text ILIKE $1
            """
            params.append(f"%{search}%")
            order_clause = " ORDER BY company_name ASC"
        else:
            base_query = """
                SELECT company_id, company_name, company_description_es, company_description_en,
                    address, company_email, product_name_es, product_name_en,
                    phone, image_url, user_name, user_email, commune_name,
                    similarity(searchable_text, $1) AS score
                FROM proveo.company_search
                WHERE searchable_text % $1
            """
            params.append(search)
            order_clause = " ORDER BY score DESC, company_name ASC"
        
        if commune:
            param_index = len(params) + 1
            base_query += f" AND LOWER(commune_name) = LOWER(${param_index})"
            params.append(commune)
        
        if product:
            idx1 = len(params) + 1
            idx2 = len(params) + 2
            base_query += (
                f" AND (LOWER(product_name_es) = LOWER(${idx1}) "
                f"OR LOWER(product_name_en) = LOWER(${idx2}))"
            )
            params.extend([product, product])
        
        limit_idx = len(params) + 1
        offset_idx = len(params) + 2
        pagination_clause = f" LIMIT ${limit_idx} OFFSET ${offset_idx}"
        params.extend([limit, offset])
        
        sql = base_query + order_clause + pagination_clause
        rows = await conn.fetch(sql, *params)
        
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append({
                "uuid": row["company_id"],
                "name": row["company_name"],
                "description": row[f"company_description_{lang}"],
                "address": row["address"],
                "email": row["company_email"],
                "product_name": row[f"product_name_{lang}"],
                "commune_name": row["commune_name"],
                "phone": row["phone"],
                "img_url": row["image_url"]
            })
        
        return results

    @staticmethod
    @db_retry()
    async def admin_delete_company_by_uuid(conn: asyncpg.Connection, company_uuid: UUID, admin_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            admin_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete companies.")

        async with transaction(conn):
            company_query = """
                SELECT uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                    description_en, address, phone, email, image_url, image_extension,
                    created_at, updated_at
                FROM proveo.companies WHERE uuid=$1
            """
            company = await conn.fetchrow(company_query, company_uuid)
            if not company:
                raise ValueError(f"Company with UUID {company_uuid} not found")

            insert_deleted = """
                INSERT INTO proveo.companies_deleted
                    (uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                    description_en, address, phone, email, image_url, image_extension,
                    created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            """
            await conn.execute(insert_deleted,
                company["uuid"], company["user_uuid"], company["product_uuid"],
                company["commune_uuid"], company["name"], company["description_es"],
                company["description_en"], company["address"], company["phone"],
                company["email"], company["image_url"], company["image_extension"],
                company["created_at"], company["updated_at"]
            )
            
            await conn.execute("DELETE FROM proveo.companies WHERE uuid=$1", company_uuid)

            logger.info("admin_deleted_company", company_uuid=str(company_uuid), admin_email=admin_email)

        image_id = company.get("image_url")
        image_ext = company.get("image_extension")
        
        if image_id and image_ext:
            image_path = f"{image_id}{image_ext}"
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(image_path),
                    timeout=15.0
                )
                if success:
                    logger.info(
                        "admin_deleted_company_image",
                        company_uuid=str(company_uuid),
                        image_path=image_path,
                        admin_email=admin_email
                    )
                else:
                    logger.warning(
                        "admin_delete_company_image_not_found",
                        company_uuid=str(company_uuid),
                        image_path=image_path,
                        admin_email=admin_email
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "admin_delete_company_image_timeout",
                    company_uuid=str(company_uuid),
                    image_path=image_path,
                    admin_email=admin_email,
                    message="Image deletion timed out after 15s - will be cleaned by cronjob"
                )
            except Exception as e:
                logger.error(
                    "admin_delete_company_image_error",
                    company_uuid=str(company_uuid),
                    image_path=image_path,
                    error=str(e),
                    admin_email=admin_email
                )

        return {
            "uuid": str(company["uuid"]),
            "name": company["name"],
            "image_url": company["image_url"]
        }