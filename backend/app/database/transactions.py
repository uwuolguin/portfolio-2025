import asyncpg
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List
from enum import Enum
from uuid import UUID
from app.database.db_retry import db_retry
from app.schemas.users import UserRecord,UserRecordHash,UserDeletionResponse,AdminUserResponse
from app.schemas.communes import CommuneRecord
from app.schemas.products import ProductRecord
from app.auth.jwt import get_password_hash
from app.config import settings
import uuid
from app.auth.csrf import generate_csrf_token
from datetime import datetime, timedelta, timezone
from app.services.image_service_client import image_service_client
import asyncio
from app.schemas.companies import (
    CompanyRecord, 
    CompanyWithRelations, 
    CompanyDeleteResponse,
    CompanySearchResponse
)

logger = structlog.get_logger(__name__)

class IsolationLevel(Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"

@asynccontextmanager
async def transaction(
    conn: asyncpg.Connection,
    isolation: IsolationLevel = IsolationLevel.READ_COMMITTED,
    readonly: bool = False,
    force_rollback: bool = False,
) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Clean asyncpg transaction wrapper with accurate commit/rollback logging.
    
    Args:
        conn: Database connection
        isolation: Transaction isolation level
        readonly: If True, transaction is read-only
        force_rollback: If True, always rollback instead of commit (for testing)
    """
    iso_mapping = {
        IsolationLevel.READ_COMMITTED: "read_committed",
        IsolationLevel.REPEATABLE_READ: "repeatable_read",
        IsolationLevel.SERIALIZABLE: "serializable",
    }

    isolation_token = iso_mapping.get(isolation)
    if isolation_token is None:
        raise ValueError(f"Unsupported isolation level: {isolation!r}")

    logger.debug(
        "transaction_started",
        isolation=isolation.value,
        readonly=readonly,
        force_rollback=force_rollback,
    )

    tx = conn.transaction(
        isolation=isolation_token,
        readonly=readonly,
    )

    await tx.start()
    
    try:
        yield conn
        
        if force_rollback:
            await tx.rollback()
            logger.debug("transaction_forced_rollback", isolation=isolation.value)
        else:
            await tx.commit()
            logger.debug("transaction_committed", isolation=isolation.value, readonly=readonly)

    except Exception as e:
        await tx.rollback()
        logger.warning(
            "transaction_rolled_back",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise

class DB:

    @staticmethod
    @db_retry()
    async def create_user(
        conn: asyncpg.Connection, 
        name: str, 
        email: str, 
        password: str,
        force_rollback: bool = False,
    ) -> UserRecord:
        hashed_password = get_password_hash(password)
        user_uuid = uuid.uuid4()
        verification_token = generate_csrf_token()
        token_expires = datetime.now(timezone.utc) + timedelta(hours=settings.verification_token_email_time)

        async with transaction(conn, force_rollback=force_rollback):
            query = """
                INSERT INTO proveo.users 
                    (uuid, name, email, hashed_password, role, verification_token, verification_token_expires)
                VALUES ($1, $2, $3, $4, 'user', $5, $6)
                ON CONFLICT (email) DO NOTHING
                RETURNING uuid, name, email, role, email_verified, verification_token, created_at
            """
            row = await conn.fetchrow(query, user_uuid, name, email, hashed_password, verification_token, token_expires)
            if not row:
                raise ValueError(f"Email {email} is already registered")

            logger.info("user_created_pending_verification", user_uuid=str(row["uuid"]), email=email)
            return UserRecord(**dict(row))

    @staticmethod
    @db_retry()
    async def get_user_by_email(conn: asyncpg.Connection, email: str) -> Optional[UserRecordHash]:
        async with transaction(conn, readonly=True):
            query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at
                FROM proveo.users
                WHERE email = $1
            """
            row = await conn.fetchrow(query, email)
            return UserRecordHash(**dict(row)) if row else None

    @staticmethod
    @db_retry()
    async def verify_email(conn: asyncpg.Connection, token: str) -> UserRecord:
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
                RETURNING uuid, name, email, role, email_verified, verification_token, created_at
            """
            verified_user = await conn.fetchrow(update_query, user['uuid'])
            logger.info("email_verified", user_uuid=str(user['uuid']), email=user['email'])
            return UserRecord(**dict(verified_user))

    @staticmethod
    @db_retry()
    async def resend_verification_email(conn: asyncpg.Connection, email: str) -> UserRecord:


        async with transaction(conn):
            query = "SELECT uuid, name, email, email_verified FROM proveo.users WHERE email = $1"
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
                RETURNING uuid, name, email, role, email_verified, verification_token, created_at
            """
            updated_user = await conn.fetchrow(update_query, verification_token, token_expires, user['uuid'])
            logger.info("verification_token_regenerated", user_uuid=str(user['uuid']), email=email)
            return UserRecord(**dict(updated_user))

    @staticmethod
    @db_retry()
    async def delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID) -> UserDeletionResponse:
        company_uuid: Optional[str] = None
        deleted_image: Optional[str] = None

        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            user_query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at
                FROM proveo.users
                WHERE uuid = $1
                FOR UPDATE
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
                FOR UPDATE
            """
            company = await conn.fetchrow(company_query, user_uuid)
            if company:
                image_id = company.get("image_url")
                image_ext = company.get("image_extension")
                deleted_image = f"{image_id}{image_ext}" if image_id and image_ext else None
                company_uuid = str(company["uuid"])
                insert_deleted_company = """
                    INSERT INTO proveo.companies_deleted
                        (uuid, user_uuid, product_uuid, commune_uuid, name, description_es,
                         description_en, address, phone, email, image_url, image_extension,
                         created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                """
                await conn.execute(insert_deleted_company,
                                   company["uuid"], company["user_uuid"], company["product_uuid"],
                                   company["commune_uuid"], company["name"], company["description_es"],
                                   company["description_en"], company["address"], company["phone"],
                                   company["email"], company["image_url"], company["image_extension"],
                                   company["created_at"], company["updated_at"])
                deleted_company = await conn.fetchrow("DELETE FROM proveo.companies WHERE uuid = $1 RETURNING uuid", company["uuid"])
                if not deleted_company:
                    raise RuntimeError("Race condition detected during company deletion")
                logger.info("user_company_deleted", user_uuid=str(user_uuid), company_uuid=company_uuid)

            insert_deleted_user = """
                INSERT INTO proveo.users_deleted
                    (uuid, name, email, hashed_password, role, email_verified, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """
            await conn.execute(insert_deleted_user,
                               user["uuid"], user["name"], user["email"], user["hashed_password"],
                               user["role"], user["email_verified"], user["created_at"])
            deleted_user = await conn.fetchrow("DELETE FROM proveo.users WHERE uuid = $1 RETURNING uuid", user_uuid)
            if not deleted_user:
                raise RuntimeError("Race condition detected during user deletion")
            logger.info("user_deleted_with_cascade", user_uuid=str(user_uuid), email=user["email"], company_deleted=1 if company else 0)

        if deleted_image:
            try:
                success = await asyncio.wait_for(image_service_client.delete_image(deleted_image), timeout=15.0)
                if success:
                    logger.info("user_self_delete_image_removed", company_uuid=company_uuid, image_path=deleted_image)
                else:
                    logger.warning("user_self_delete_image_not_found", company_uuid=company_uuid, image_path=deleted_image)
            except asyncio.TimeoutError:
                logger.warning("user_self_delete_image_timeout", company_uuid=company_uuid, image_path=deleted_image)
            except Exception as e:
                logger.error("user_self_delete_image_error", company_uuid=company_uuid, image_path=deleted_image, error=str(e), exc_info=True)

        return UserDeletionResponse(
            user_uuid=user_uuid,
            email=user["email"],
            company_deleted=1 if company else 0,
            image_deleted=1 if deleted_image else 0
        )

    @staticmethod
    @db_retry()
    async def get_all_users_admin(conn: asyncpg.Connection, limit: int = 100, offset: int = 0) -> List[AdminUserResponse]:
        async with transaction(conn, readonly=True):
            query = """
                SELECT u.uuid, u.name, u.email, u.role, u.email_verified, u.created_at,
                       COUNT(c.uuid) AS company_count
                FROM proveo.users u
                LEFT JOIN proveo.companies c ON c.user_uuid = u.uuid
                GROUP BY u.uuid
                ORDER BY u.created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)
            return [AdminUserResponse(**dict(row)) for row in rows]

    @staticmethod
    @db_retry()
    async def admin_delete_user_by_uuid(conn: asyncpg.Connection, user_uuid: UUID) -> UserDeletionResponse:
        deleted_image_path: Optional[str] = None
        company_uuid: Optional[str] = None

        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            user_query = """
                SELECT uuid, name, email, hashed_password, role, email_verified, created_at
                FROM proveo.users
                WHERE uuid = $1
                FOR UPDATE
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
                FOR UPDATE
            """
            company = await conn.fetchrow(company_query, user_uuid)

            if company:
                image_id = company.get("image_url")
                image_ext = company.get("image_extension")
                deleted_image_path = f"{image_id}{image_ext}" if image_id and image_ext else None
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

                deleted_company = await conn.fetchrow(
                    "DELETE FROM proveo.companies WHERE uuid = $1 RETURNING uuid", company["uuid"]
                )
                if not deleted_company:
                    raise RuntimeError("Race condition detected during company deletion")

                logger.info("user_company_deleted", user_uuid=str(user_uuid), company_uuid=company_uuid)

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

            deleted_user = await conn.fetchrow(
                "DELETE FROM proveo.users WHERE uuid = $1 RETURNING uuid", user_uuid
            )
            if not deleted_user:
                raise RuntimeError("Race condition detected during user deletion")

            logger.info(
                "user_deleted_with_cascade",
                user_uuid=str(user_uuid),
                email=user["email"],
                company_deleted=1 if company else 0
            )

        if deleted_image_path:
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(deleted_image_path),
                    timeout=15.0
                )
                if success:
                    logger.info("user_image_removed", company_uuid=company_uuid, image_path=deleted_image_path)
                else:
                    logger.warning("user_image_not_found", company_uuid=company_uuid, image_path=deleted_image_path)
            except asyncio.TimeoutError:
                logger.warning("user_image_timeout", company_uuid=company_uuid, image_path=deleted_image_path)
            except Exception as e:
                logger.error("user_image_error", company_uuid=company_uuid, image_path=deleted_image_path, error=str(e), exc_info=True)

        return UserDeletionResponse(
            user_uuid=user_uuid,
            email=user["email"],
            company_deleted=1 if company else 0,
            image_deleted=1 if deleted_image_path else 0
        )
             
    @staticmethod
    @db_retry()
    async def get_all_products(conn: asyncpg.Connection) -> List[ProductRecord]:
        """
        Get all products ordered by English name
        
        Returns:
            List of ProductRecord objects (not Dict)
        
        Note: Matches communes pattern for consistency
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            query = """
                SELECT uuid, name_es, name_en, created_at
                FROM proveo.products
                ORDER BY name_en ASC
            """
            rows = await conn.fetch(query)
            return [ProductRecord(**dict(row)) for row in rows]

    @staticmethod
    @db_retry()
    async def create_product(conn: asyncpg.Connection, name_es: str, name_en: str,force_rollback: bool = False) -> ProductRecord:
        product_uuid = str(uuid.uuid4())

        try:
            async with transaction(conn,force_rollback=force_rollback):
                row = await conn.fetchrow(
                    """
                    INSERT INTO proveo.products (uuid, name_es, name_en)
                    VALUES ($1, $2, $3)
                    RETURNING uuid, name_es, name_en, created_at
                    """,
                    product_uuid,
                    name_es,
                    name_en,
                )

                logger.info("product_created", product_uuid=str(row["uuid"]))
                return ProductRecord(**dict(row))

        except asyncpg.UniqueViolationError:
            raise ValueError("Product with this name already exists")

    @staticmethod
    @db_retry()
    async def update_product_by_uuid(
        conn: asyncpg.Connection,
        product_uuid: UUID,
        name_es: str,
        name_en: str,
    ) -> ProductRecord:

        async with transaction(conn):
            existing = await conn.fetchval(
                "SELECT 1 FROM proveo.products WHERE uuid=$1",
                product_uuid,
            )
            if not existing:
                raise ValueError(f"Product with UUID {product_uuid} not found")

            conflict_es = await conn.fetchval(
                "SELECT 1 FROM proveo.products WHERE name_es=$1 AND uuid!=$2",
                name_es,
                product_uuid,
            )
            if conflict_es:
                raise ValueError(
                    f"Another product with Spanish name '{name_es}' already exists"
                )

            conflict_en = await conn.fetchval(
                "SELECT 1 FROM proveo.products WHERE name_en=$1 AND uuid!=$2",
                name_en,
                product_uuid,
            )
            if conflict_en:
                raise ValueError(
                    f"Another product with English name '{name_en}' already exists"
                )

            row = await conn.fetchrow(
                """
                UPDATE proveo.products
                SET name_es=$1, name_en=$2
                WHERE uuid=$3
                RETURNING uuid, name_es, name_en, created_at
                """,
                name_es,
                name_en,
                product_uuid,
            )

            logger.info("product_updated", product_uuid=str(product_uuid))
            return ProductRecord(**dict(row))


    @staticmethod
    @db_retry()
    async def delete_product_by_uuid(
        conn: asyncpg.Connection, 
        product_uuid: UUID
    ) -> ProductRecord:
        """
        Delete product by UUID (soft delete to products_deleted table)
        
        Args:
            conn: Database connection
            product_uuid: Product UUID to delete
        
        Returns:
            ProductRecord object (the deleted product)
        
        Raises:
            ValueError: If product not found or still in use by companies
        
        Note: Admin validation must be done in router layer
        """
        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            product_query = """
                SELECT uuid, name_es, name_en, created_at 
                FROM proveo.products 
                WHERE uuid=$1
            """
            product = await conn.fetchrow(product_query, product_uuid)
            
            if not product:
                raise ValueError(f"Product with UUID {product_uuid} not found")
            
            company_count = await conn.fetchval(
                "SELECT COUNT(*) FROM proveo.companies WHERE product_uuid=$1", 
                product_uuid
            )
            
            if company_count > 0:
                raise ValueError(
                    f"Cannot delete product '{product['name_en']}'. "
                    f"{company_count} company(ies) are still using this product."
                )
            
            insert_deleted = """
                INSERT INTO proveo.products_deleted (uuid, name_es, name_en, created_at) 
                VALUES ($1, $2, $3, $4)
            """
            await conn.execute(
                insert_deleted, 
                product["uuid"], 
                product["name_es"], 
                product["name_en"], 
                product["created_at"]
            )
            
            await conn.execute("DELETE FROM proveo.products WHERE uuid=$1", product_uuid)
            
            logger.info("product_deleted", product_uuid=str(product_uuid))
            
            return ProductRecord(**dict(product))

    @staticmethod
    @db_retry()
    async def get_all_communes(conn: asyncpg.Connection) -> List[CommuneRecord]:
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            query = """
                SELECT uuid, name, created_at
                FROM proveo.communes
                ORDER BY name ASC
            """
            rows = await conn.fetch(query)
            return [CommuneRecord(**dict(row)) for row in rows]

    @staticmethod
    @db_retry()
    async def create_commune(conn: asyncpg.Connection, name: str,force_rollback: bool = False) -> CommuneRecord:        
        commune_uuid = str(uuid.uuid4())
        async with transaction(conn,force_rollback=force_rollback):
            insert_query = """
                INSERT INTO proveo.communes (name,uuid) 
                VALUES ($1,$2) 
                ON CONFLICT (name) DO NOTHING
                RETURNING uuid,name,created_at
            """
            row = await conn.fetchrow(insert_query, name, commune_uuid)
            
            if row is None:
                raise ValueError(f"Commune with name '{name}' already exists")
            
            logger.info("commune_created", uuid=commune_uuid)
            return CommuneRecord(**dict(row))

    @staticmethod
    @db_retry()
    async def update_commune_by_uuid(conn: asyncpg.Connection, commune_uuid: UUID, name: str) -> CommuneRecord:        
        async with transaction(conn):
            existing = await conn.fetchval("SELECT 1 FROM proveo.communes WHERE uuid=$1", commune_uuid)
            if not existing:
                raise ValueError(f"Commune with UUID {commune_uuid} not found")
            
            if name is None:
                raise ValueError("Name is required for update")
            conflict = await conn.fetchval(
                "SELECT 1 FROM proveo.communes WHERE name=$1 AND uuid!=$2", 
                name, commune_uuid
            )
            if conflict:
                raise ValueError(f"Another commune with name '{name}' already exists")
            
            update_query = "UPDATE proveo.communes SET name=$1 WHERE uuid=$2 RETURNING uuid,name,created_at"
            row = await conn.fetchrow(update_query, name, commune_uuid)
            
            logger.info("commune_updated", commune_uuid=str(commune_uuid))
            return CommuneRecord(**dict(row))

    @staticmethod
    @db_retry()
    async def delete_commune_by_uuid(conn: asyncpg.Connection, commune_uuid: UUID) -> CommuneRecord:
        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            commune_query = """
                SELECT uuid, name, created_at
                FROM proveo.communes
                WHERE uuid = $1
            """
            commune = await conn.fetchrow(commune_query, commune_uuid)
            if not commune:
                raise ValueError(f"Commune with UUID {commune_uuid} not found")

            company_count = await conn.fetchval(
                "SELECT COUNT(*) FROM proveo.companies WHERE commune_uuid = $1",
                commune_uuid,
            )
            if company_count > 0:
                raise ValueError(
                    f"Cannot delete commune '{commune['name']}'. {company_count} company(ies) are still located in this commune."
                )

            await conn.execute(
                "INSERT INTO proveo.communes_deleted (uuid, name, created_at) VALUES ($1, $2, $3)",
                commune["uuid"],
                commune["name"],
                commune["created_at"],
            )

            await conn.execute(
                "DELETE FROM proveo.communes WHERE uuid = $1",
                commune_uuid,
            )

            logger.info("commune_deleted", commune_uuid=str(commune_uuid))

            return CommuneRecord(
                uuid=str(commune["uuid"]),
                name=commune["name"],
                created_at=commune["created_at"]
            )

    @staticmethod
    @db_retry()
    async def get_company_by_uuid(
        conn: asyncpg.Connection, 
        company_uuid: UUID
    ) -> Optional[CompanyWithRelations]:
        """
        Get a single company by UUID with all related data.
        
        Args:
            conn: Database connection
            company_uuid: Company UUID
            
        Returns:
            CompanyWithRelations if found, None otherwise
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            query = """
                SELECT 
                    c.uuid, c.user_uuid, c.product_uuid, c.commune_uuid, 
                    c.name, c.description_es, c.description_en,
                    c.address, c.phone, c.email, c.image_url, c.image_extension, 
                    c.created_at, c.updated_at,
                    u.name as user_name, u.email as user_email,
                    p.name_es as product_name_es, p.name_en as product_name_en,
                    cm.name as commune_name
                FROM proveo.companies c
                LEFT JOIN proveo.users u ON u.uuid = c.user_uuid
                LEFT JOIN proveo.products p ON p.uuid = c.product_uuid
                LEFT JOIN proveo.communes cm ON cm.uuid = c.commune_uuid
                WHERE c.uuid = $1
            """
            row = await conn.fetchrow(query, company_uuid)
            
            if not row:
                return None
                
            return CompanyWithRelations(**dict(row))

    @staticmethod
    @db_retry()
    async def get_all_companies(
        conn: asyncpg.Connection, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[CompanyWithRelations]:
        """
        Get all companies with pagination.
        
        Args:
            conn: Database connection
            limit: Number of companies to return
            offset: Number of companies to skip
            
        Returns:
            List of CompanyWithRelations
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            query = """
                SELECT 
                    c.uuid, c.user_uuid, c.product_uuid, c.commune_uuid,
                    c.name, c.description_es, c.description_en,
                    c.address, c.phone, c.email, c.image_url, c.image_extension,
                    c.created_at, c.updated_at,
                    u.name as user_name, u.email as user_email,
                    p.name_es as product_name_es, p.name_en as product_name_en,
                    cm.name as commune_name
                FROM proveo.companies c
                LEFT JOIN proveo.users u ON u.uuid = c.user_uuid
                LEFT JOIN proveo.products p ON p.uuid = c.product_uuid
                LEFT JOIN proveo.communes cm ON cm.uuid = c.commune_uuid
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)
            return [CompanyWithRelations(**dict(row)) for row in rows]

    @staticmethod
    @db_retry()
    async def get_company_by_user_uuid(
        conn: asyncpg.Connection, 
        user_uuid: UUID
    ) -> CompanyWithRelations | None:
        """
        Get all companies belonging to a specific user.
        
        Args:
            conn: Database connection
            user_uuid: User UUID
            
        Returns:
            List of CompanyWithRelations (Just one due to business rule)
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            query = """
                SELECT 
                    c.uuid, c.user_uuid, c.product_uuid, c.commune_uuid,
                    c.name, c.description_es, c.description_en,
                    c.address, c.phone, c.email, c.image_url, c.image_extension,
                    c.created_at, c.updated_at,
                    u.name as user_name, u.email as user_email,
                    p.name_es as product_name_es, p.name_en as product_name_en,
                    cm.name as commune_name
                FROM proveo.companies c
                LEFT JOIN proveo.users u ON u.uuid = c.user_uuid
                LEFT JOIN proveo.products p ON p.uuid = c.product_uuid
                LEFT JOIN proveo.communes cm ON cm.uuid = c.commune_uuid
                WHERE c.user_uuid = $1
                ORDER BY c.created_at DESC
            """
            row = await conn.fetchrow(query, user_uuid)
            if row is None:
                return None
            return CompanyWithRelations(**dict(row))

    @staticmethod
    @db_retry()
    async def create_company(
        conn: asyncpg.Connection,
        company_uuid: UUID,
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
        force_rollback: bool = False,
    ) -> CompanyRecord:
        """
        Create a new company.
        
        Args:
            conn: Database connection
            company_uuid: Pre-generated UUID for the company
            user_uuid: Owner's UUID
            product_uuid: Product category UUID
            commune_uuid: Location UUID
            name: Company name
            description_es: Spanish description
            description_en: English description
            address: Physical address
            phone: Contact phone
            email: Contact email
            image_url: Image identifier (UUID)
            image_extension: Image file extension (.jpg, .png)
            force_rollback: If True, rollback transaction (for testing)
            
        Returns:
            CompanyRecord of the created company
            
        Raises:
            ValueError: If business rules violated or foreign keys invalid
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, force_rollback=force_rollback):
            existing_company = await conn.fetchval(
                "SELECT 1 FROM proveo.companies WHERE user_uuid=$1",
                user_uuid
            )
            if existing_company:
                raise ValueError(
                    "Each user can only create one company. "
                    "Please update your existing company."
                )
            
            product_exists = await conn.fetchval(
                "SELECT 1 FROM proveo.products WHERE uuid=$1", 
                product_uuid
            )
            if not product_exists:
                raise ValueError(f"Product with UUID {product_uuid} does not exist")
            
            commune_exists = await conn.fetchval(
                "SELECT 1 FROM proveo.communes WHERE uuid=$1", 
                commune_uuid
            )
            if not commune_exists:
                raise ValueError(f"Commune with UUID {commune_uuid} does not exist")
            
            insert_query = """
                INSERT INTO proveo.companies (
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING 
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension,
                    created_at, updated_at
            """
            row = await conn.fetchrow(
                insert_query,
                company_uuid, user_uuid, product_uuid, commune_uuid,
                name, description_es, description_en,
                address, phone, email, image_url, image_extension
            )

            logger.info(
                "company_created", 
                company_uuid=str(company_uuid), 
                user_uuid=str(user_uuid)
            )

            return CompanyRecord(**dict(row))

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
    ) -> CompanyRecord:
        """
        Update an existing company.
        
        Args:
            conn: Database connection
            company_uuid: Company UUID to update
            user_uuid: User UUID (for ownership verification)
            (all other args): Optional fields to update
            
        Returns:
            CompanyRecord with updated data
            
        Raises:
            ValueError: If company not found or invalid data
            PermissionError: If user doesn't own the company
        """
        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED):
            owner_check = await conn.fetchval(
                "SELECT user_uuid FROM proveo.companies WHERE uuid=$1", 
                company_uuid
            )
            if not owner_check:
                raise ValueError(f"Company with UUID {company_uuid} not found")
            if owner_check != user_uuid:
                raise PermissionError("You can only update your own companies")

            update_fields = []
            params = []
            param_count = 1

            def is_empty(val):
                return val is None or (isinstance(val, str) and val.strip() == "")

            field_mapping = [
                ("name", name),
                ("description_es", description_es),
                ("description_en", description_en),
                ("address", address),
                ("phone", phone),
                ("image_url", image_url),
                ("image_extension", image_extension)
            ]

            for field_name, value in field_mapping:
                if not is_empty(value):
                    update_fields.append(f"{field_name}=${param_count}")
                    params.append(value.strip() if isinstance(value, str) else value)
                    param_count += 1

            if not is_empty(email):
                email_stripped = email.strip()
                if "@" not in email_stripped or "." not in email_stripped:
                    raise ValueError("Invalid email format")
                update_fields.append(f"email=${param_count}")
                params.append(email_stripped)
                param_count += 1

            if product_uuid is not None:
                product_exists = await conn.fetchval(
                    "SELECT 1 FROM proveo.products WHERE uuid=$1", 
                    product_uuid
                )
                if not product_exists:
                    raise ValueError(f"Product with UUID {product_uuid} does not exist")
                update_fields.append(f"product_uuid=${param_count}")
                params.append(product_uuid)
                param_count += 1

            if commune_uuid is not None:
                commune_exists = await conn.fetchval(
                    "SELECT 1 FROM proveo.communes WHERE uuid=$1", 
                    commune_uuid
                )
                if not commune_exists:
                    raise ValueError(f"Commune with UUID {commune_uuid} does not exist")
                update_fields.append(f"commune_uuid=${param_count}")
                params.append(commune_uuid)
                param_count += 1

            if not update_fields:
                raise ValueError("No fields provided for update")

            update_fields.append("updated_at=NOW()")

            where_idx = len(params) + 1
            params.append(company_uuid)

            update_query = f"""
                UPDATE proveo.companies
                SET {', '.join(update_fields)}
                WHERE uuid=${where_idx}
                RETURNING 
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension,
                    created_at, updated_at
            """
            row = await conn.fetchrow(update_query, *params)
            
            if not row:
                raise RuntimeError("Failed to update company")

            logger.info(
                "company_updated", 
                company_uuid=str(company_uuid), 
                user_uuid=str(user_uuid),
                fields_updated=len(update_fields)
            )
            
            return CompanyRecord(**dict(row))

    @staticmethod
    @db_retry()
    async def delete_company_by_uuid(
        conn: asyncpg.Connection, 
        company_uuid: UUID, 
        user_uuid: UUID
    ) -> CompanyDeleteResponse:
        """
        Delete a company (soft delete to companies_deleted table).
        Also schedules image deletion from storage.
        
        Args:
            conn: Database connection
            company_uuid: Company UUID to delete
            user_uuid: User UUID (for ownership verification)
            
        Returns:
            CompanyDeleteResponse with deletion details
            
        Raises:
            ValueError: If company not found
            PermissionError: If user doesn't own the company
        """
        deleted_image: str | None = None
        
        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            company_query = """
                SELECT 
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension,
                    created_at, updated_at
                FROM proveo.companies 
                WHERE uuid = $1 AND user_uuid = $2
            """
            company = await conn.fetchrow(company_query, company_uuid, user_uuid)
            
            if not company:
                logger.warning(
                    "company_not_found_or_unauthorized",
                    company_uuid=str(company_uuid),
                    user_uuid=str(user_uuid)
                )
                raise ValueError(
                    f"Company with UUID {company_uuid} not found or "
                    "you don't have permission to delete it"
                )
            
            insert_deleted = """
                INSERT INTO proveo.companies_deleted (
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension, 
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """
            await conn.execute(
                insert_deleted,
                company["uuid"], company["user_uuid"], company["product_uuid"],
                company["commune_uuid"], company["name"], company["description_es"],
                company["description_en"], company["address"], company["phone"],
                company["email"], company["image_url"], company["image_extension"],
                company["created_at"], company["updated_at"]
            )

            delete_query = "DELETE FROM proveo.companies WHERE uuid = $1 RETURNING uuid"
            deleted_row = await conn.fetchrow(delete_query, company_uuid)

            if not deleted_row:
                logger.error(
                    "company_delete_race_condition",
                    company_uuid=str(company_uuid)
                )
                raise RuntimeError("Race condition detected during company deletion")
            
            logger.info(
                "company_deleted_successfully",
                company_uuid=str(company_uuid),
                user_uuid=str(user_uuid)
            )

            image_id = company.get("image_url")
            image_ext = company.get("image_extension")
            if image_id and image_ext:
                deleted_image = f"{image_id}{image_ext}"

        if deleted_image:
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(deleted_image),
                    timeout=15.0
                )
                if success:
                    logger.info(
                        "company_image_deleted",
                        company_uuid=str(company_uuid),
                        image_path=deleted_image
                    )
                else:
                    logger.warning(
                        "company_image_not_found",
                        company_uuid=str(company_uuid),
                        image_path=deleted_image
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "company_image_delete_timeout",
                    company_uuid=str(company_uuid),
                    image_path=deleted_image
                )
            except Exception as e:
                logger.error(
                    "company_image_delete_error",
                    company_uuid=str(company_uuid),
                    image_path=deleted_image,
                    error=str(e),
                    exc_info=True
                )

        return CompanyDeleteResponse(
            uuid=company_uuid,
            name=company["name"]
        )

    @staticmethod
    @db_retry()
    async def admin_delete_company_by_uuid(
        conn: asyncpg.Connection, 
        company_uuid: UUID
    ) -> CompanyDeleteResponse:
        """
        Admin-level company deletion (bypasses ownership check).
        
        Args:
            conn: Database connection
            company_uuid: Company UUID to delete
            
        Returns:
            CompanyDeleteResponse with deletion details
            
        Raises:
            ValueError: If company not found
            
        Note: Caller must verify admin role before calling this function
        """
        deleted_image_path: Optional[str] = None

        async with transaction(conn, isolation=IsolationLevel.SERIALIZABLE):
            company_query = """
                SELECT 
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension,
                    created_at, updated_at
                FROM proveo.companies 
                WHERE uuid=$1
            """
            company = await conn.fetchrow(company_query, company_uuid)
            
            if not company:
                raise ValueError(f"Company with UUID {company_uuid} not found")

            insert_deleted = """
                INSERT INTO proveo.companies_deleted (
                    uuid, user_uuid, product_uuid, commune_uuid,
                    name, description_es, description_en,
                    address, phone, email, image_url, image_extension,
                    created_at, updated_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            """
            await conn.execute(
                insert_deleted,
                company["uuid"], company["user_uuid"], company["product_uuid"],
                company["commune_uuid"], company["name"], company["description_es"],
                company["description_en"], company["address"], company["phone"],
                company["email"], company["image_url"], company["image_extension"],
                company["created_at"], company["updated_at"]
            )
            
            deleted_company = await conn.fetchrow(
                "DELETE FROM proveo.companies WHERE uuid=$1 RETURNING uuid", 
                company_uuid
            )
            
            if not deleted_company:
                raise RuntimeError("Race condition detected during company deletion")
            
            logger.info("admin_deleted_company", company_uuid=str(company_uuid))

            image_id = company.get("image_url")
            image_ext = company.get("image_extension")
            if image_id and image_ext:
                deleted_image_path = f"{image_id}{image_ext}"

        if deleted_image_path:
            try:
                success = await asyncio.wait_for(
                    image_service_client.delete_image(deleted_image_path),
                    timeout=15.0
                )
                if success:
                    logger.info(
                        "admin_deleted_company_image",
                        company_uuid=str(company_uuid),
                        image_path=deleted_image_path
                    )
                else:
                    logger.warning(
                        "admin_delete_company_image_not_found",
                        company_uuid=str(company_uuid),
                        image_path=deleted_image_path
                    )
            except asyncio.TimeoutError:
                logger.warning(
                    "admin_delete_company_image_timeout",
                    company_uuid=str(company_uuid),
                    image_path=deleted_image_path
                )
            except Exception as e:
                logger.error(
                    "admin_delete_company_image_error",
                    company_uuid=str(company_uuid),
                    image_path=deleted_image_path,
                    error=str(e),
                    exc_info=True
                )

        return CompanyDeleteResponse(
            uuid=company_uuid,
            name=company["name"]
        )

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
    ) -> List[CompanySearchResponse]:
        """
        Search companies using materialized view with trigram similarity.
        
        Args:
            conn: Database connection
            query: Search text
            lang: Language for response ('es' or 'en')
            commune: Optional commune filter
            product: Optional product filter
            limit: Max results to return
            offset: Results to skip (pagination)
            
        Returns:
            List of CompanySearchResponse objects
        """
        search = (query or "").strip().lower()
        params: List = []

        async with transaction(conn, isolation=IsolationLevel.READ_COMMITTED, readonly=True):
            if not search:
                base_query = """
                    SELECT 
                        company_id, company_name, company_description_es,
                        company_description_en, address, company_email,
                        product_name_es, product_name_en, phone, image_url,
                        user_name, user_email, commune_name
                    FROM proveo.company_search
                    WHERE 1=1
                """
                order_clause = " ORDER BY company_name ASC"
            elif len(search) < 4:
                base_query = """
                    SELECT 
                        company_id, company_name, company_description_es,
                        company_description_en, address, company_email,
                        product_name_es, product_name_en, phone, image_url,
                        user_name, user_email, commune_name
                    FROM proveo.company_search
                    WHERE searchable_text ILIKE $1
                """
                params.append(f"%{search}%")
                order_clause = " ORDER BY company_name ASC"
            else:
                base_query = """
                    SELECT 
                        company_id, company_name, company_description_es,
                        company_description_en, address, company_email,
                        product_name_es, product_name_en, phone, image_url,
                        user_name, user_email, commune_name,
                        similarity(searchable_text, $1) AS score
                    FROM proveo.company_search
                    WHERE 1=1
                """
                params.append(search)
                order_clause = " ORDER BY score DESC, company_name ASC"

            if commune:
                next_param = len(params) + 1
                base_query += f" AND LOWER(commune_name) = LOWER(${next_param})"
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

            results: List[CompanySearchResponse] = []
            for row in rows:
                results.append(CompanySearchResponse(
                    uuid=row["company_id"],
                    name=row["company_name"],
                    description=row[f"company_description_{lang}"],
                    address=row["address"],
                    email=row["company_email"],
                    product_name=row[f"product_name_{lang}"],
                    commune_name=row["commune_name"],
                    phone=row["phone"],
                    img_url=row["image_url"]
                ))

            return results