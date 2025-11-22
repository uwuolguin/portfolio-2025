import asyncpg
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List, Dict, Any
from enum import Enum
from uuid import UUID
from app.utils.db_retry import db_retry
from app.auth.jwt import get_password_hash
from app.config import settings
import uuid
from app.auth.csrf import generate_csrf_token
from datetime import datetime,timedelta,timezone
from app.utils.file_handler import FileHandler

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
    async def delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID) -> Dict[str, Any]:
        """User deletes their own account"""
        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            user_query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at 
                FROM proveo.users 
                WHERE uuid = $1
            """
            user = await conn.fetchrow(user_query, user_uuid)
            if not user:
                raise ValueError(f"User with UUID {user_uuid} not found")
            
            companies_query = """
                SELECT uuid, user_uuid, product_uuid, commune_uuid, name, description_es, 
                    description_en, address, phone, email, image_url, image_extension, 
                    created_at, updated_at
                FROM proveo.companies
                WHERE user_uuid = $1
            """
            companies = await conn.fetch(companies_query, user_uuid)
            
            if companies:
                deleted_images = []
                for company in companies:
                    image_id = company.get("image_url")  # This is company_uuid
                    image_ext = company.get("image_extension")  # e.g., ".jpg"
                    
                    if image_id and image_ext:
                        success = await FileHandler.delete_image(image_id, image_ext)
                        if success:
                            deleted_images.append(f"{image_id}{image_ext}")
                            logger.info(
                                "user_self_delete_image_removed",
                                company_uuid=str(company["uuid"]),
                                image_path=f"{image_id}{image_ext}"
                            )
                        else:
                            logger.warning(
                                "user_self_delete_image_not_found",
                                company_uuid=str(company["uuid"]),
                                image_path=f"{image_id}{image_ext}"
                            )
                
                delete_companies_query = """
                    INSERT INTO proveo.companies_deleted 
                        (uuid, user_uuid, product_uuid, commune_uuid, name, description_es, 
                        description_en, address, phone, email, image_url, image_extension,
                        created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """
                for company in companies:
                    await conn.execute(delete_companies_query,
                        company["uuid"], company["user_uuid"], company["product_uuid"],
                        company["commune_uuid"], company["name"], company["description_es"],
                        company["description_en"], company["address"], company["phone"],
                        company["email"], company["image_url"], company["image_extension"],
                        company["created_at"], company["updated_at"]
                    )
                
                await conn.execute("DELETE FROM proveo.companies WHERE user_uuid = $1", user_uuid)
                await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search")
                
                logger.info(
                    "user_companies_deleted", 
                    user_uuid=str(user_uuid), 
                    companies_count=len(companies),
                    images_deleted=len(deleted_images)
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
            
            await conn.execute("DELETE FROM proveo.users WHERE uuid = $1", user_uuid)
            
            logger.info(
                "user_deleted_with_cascade", 
                user_uuid=str(user_uuid), 
                email=user["email"], 
                companies_deleted=len(companies)
            )
            
            return {
                "user_uuid": str(user_uuid), 
                "email": user["email"], 
                "companies_deleted": len(companies)
            }


    @staticmethod
    @db_retry()
    async def admin_delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID, admin_email: str) -> Dict[str, Any]:
        """Admin deletes another user's account"""
        # Verify admin permissions
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            admin_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete other users.")
        
        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
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
                deleted_images = []
                for company in companies:
                    image_id = company.get("image_url")  # This is company_uuid
                    image_ext = company.get("image_extension")  # e.g., ".jpg"
                    
                    if image_id and image_ext:
                        success = await FileHandler.delete_image(image_id, image_ext)
                        if success:
                            deleted_images.append(f"{image_id}{image_ext}")
                            logger.info(
                                "admin_delete_user_image_removed",
                                company_uuid=str(company["uuid"]),
                                image_path=f"{image_id}{image_ext}",
                                admin_email=admin_email
                            )
                        else:
                            logger.warning(
                                "admin_delete_user_image_not_found",
                                company_uuid=str(company["uuid"]),
                                image_path=f"{image_id}{image_ext}",
                                admin_email=admin_email
                            )
                
                delete_companies_query = """
                    INSERT INTO proveo.companies_deleted
                        (uuid, user_uuid, product_uuid, commune_uuid, name, description_es, 
                        description_en, address, phone, email, image_url, image_extension,
                        created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """
                for company in companies:
                    await conn.execute(delete_companies_query,
                        company["uuid"], company["user_uuid"], company["product_uuid"],
                        company["commune_uuid"], company["name"], company["description_es"],
                        company["description_en"], company["address"], company["phone"],
                        company["email"], company["image_url"], company["image_extension"],
                        company["created_at"], company["updated_at"]
                    )
                
                await conn.execute("DELETE FROM proveo.companies WHERE user_uuid=$1", user_uuid)
                
                logger.info(
                    "admin_deleted_user_companies", 
                    user_uuid=str(user_uuid), 
                    companies_count=len(companies),
                    images_deleted=len(deleted_images),
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
            
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search")
            
            return {
                "user_uuid": str(user_uuid), 
                "email": user["email"], 
                "companies_deleted": len(companies)
            }


    @staticmethod
    @db_retry()
    async def admin_delete_company_by_uuid(conn: asyncpg.Connection, company_uuid: UUID, admin_email: str) -> Dict[str, Any]:
        admin_user = await conn.fetchrow(
            "SELECT role FROM proveo.users WHERE email = $1", 
            admin_email
        )
        if not admin_user or admin_user['role'] != 'admin':
            raise PermissionError("Only admin users can delete other users.")

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

            # Delete image from image service
            image_id = company.get("image_url")  # This is company_uuid
            image_ext = company.get("image_extension")  # e.g., ".jpg"
            
            if image_id and image_ext:
                success = await FileHandler.delete_image(image_id, image_ext)
                if success:
                    logger.info(
                        "admin_deleted_company_image",
                        company_uuid=str(company_uuid),
                        image_path=f"{image_id}{image_ext}",
                        admin_email=admin_email
                    )
                else:
                    logger.warning(
                        "admin_delete_company_image_not_found",
                        company_uuid=str(company_uuid),
                        image_path=f"{image_id}{image_ext}",
                        admin_email=admin_email
                    )

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
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search")

            logger.info("admin_deleted_company", company_uuid=str(company_uuid), admin_email=admin_email)

            return {
                "uuid": str(company["uuid"]),
                "name": company["name"],
                "image_url": company["image_url"]
            }