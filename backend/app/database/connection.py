"""
Database Connection Pool Manager with Read/Write Splitting

This module provides separate connection pools for:
- WRITE operations (INSERT, UPDATE, DELETE) -> Primary database
- READ operations (SELECT) -> Replica database (falls back to primary if unavailable)

Architecture:
- write_pool: Connects to postgres-primary for all write operations
- read_pool: Connects to postgres-replica for read operations
- Automatic fallback: If replica is unavailable, reads go to primary
"""

import ssl
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class DatabasePoolManager:
    """
    Manages separate connection pools for read and write operations.
    
    Usage:
        # For writes (INSERT, UPDATE, DELETE, DDL)
        async with pool_manager.acquire_write() as conn:
            await conn.execute("INSERT INTO ...")
        
        # For reads (SELECT)
        async with pool_manager.acquire_read() as conn:
            await conn.fetch("SELECT * FROM ...")
    """
    
    write_pool: Optional[asyncpg.Pool] = None
    read_pool: Optional[asyncpg.Pool] = None
    _replica_available: bool = False

    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context for database connections"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize connection settings"""
        await conn.execute("SET timezone TO 'UTC'")
        await conn.execute(f"SET statement_timeout TO '{settings.db_timeout}s'")
        await conn.execute("SET log_statement_stats TO off")
        await conn.execute("SET pg_trgm.similarity_threshold = 0.15")

        if settings.debug:
            await conn.execute(
                f"SET log_min_duration_statement TO "
                f"{int(settings.db_slow_query_threshold * 1000)}"
            )

    async def init_pools(self) -> None:
        """Initialize both write and read connection pools"""
        ssl_context = self._create_ssl_context()
        
        # Initialize WRITE pool (primary)
        try:
            self.write_pool = await asyncpg.create_pool(
                dsn=settings.database_url_primary,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                max_queries=settings.db_pool_max_queries,
                max_inactive_connection_lifetime=settings.db_pool_max_inactive,
                command_timeout=settings.db_command_timeout,
                server_settings={
                    "application_name": f"{settings.project_name}_write",
                    "tcp_keepalives_idle": "600",
                    "tcp_keepalives_interval": "30",
                    "tcp_keepalives_count": "3",
                },
                ssl=ssl_context,
                init=self._init_connection,
            )
            logger.info(
                "write_pool_initialized",
                pool_size=self.write_pool.get_size(),
                host="postgres-primary",
            )
        except Exception as e:
            logger.error(
                "write_pool_init_failed",
                error=str(e),
                exc_info=True,
            )
            raise

        # Initialize READ pool (replica)
        try:
            self.read_pool = await asyncpg.create_pool(
                dsn=settings.database_url_replica,
                min_size=max(1, settings.db_pool_min_size // 2),
                max_size=settings.db_pool_max_size,
                max_queries=settings.db_pool_max_queries,
                max_inactive_connection_lifetime=settings.db_pool_max_inactive,
                command_timeout=settings.db_command_timeout,
                server_settings={
                    "application_name": f"{settings.project_name}_read",
                    "tcp_keepalives_idle": "600",
                    "tcp_keepalives_interval": "30",
                    "tcp_keepalives_count": "3",
                },
                ssl=ssl_context,
                init=self._init_connection,
            )
            
            # Verify replica is actually in recovery mode
            async with self.read_pool.acquire() as conn:
                is_replica = await conn.fetchval("SELECT pg_is_in_recovery()")
                if is_replica:
                    self._replica_available = True
                    logger.info(
                        "read_pool_initialized",
                        pool_size=self.read_pool.get_size(),
                        host="postgres-replica",
                        is_replica=True,
                    )
                else:
                    logger.warning(
                        "read_pool_not_replica",
                        message="Read pool connected but target is not a replica. Using primary for reads.",
                    )
                    self._replica_available = False
                    
        except Exception as e:
            logger.warning(
                "read_pool_init_failed_using_primary",
                error=str(e),
                message="Replica unavailable, reads will use primary",
            )
            self._replica_available = False
            self.read_pool = None

    async def close_pools(self) -> None:
        """Close all connection pools"""
        if self.write_pool:
            await self.write_pool.close()
            self.write_pool = None
            
        if self.read_pool:
            await self.read_pool.close()
            self.read_pool = None
            
        self._replica_available = False
        logger.info("database_pools_closed")

    @asynccontextmanager
    async def acquire_write(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire a connection for WRITE operations.
        Always uses the primary database.
        """
        if not self.write_pool:
            raise RuntimeError("Write pool not initialized")

        async with self.write_pool.acquire() as conn:
            try:
                yield conn
            except Exception as e:
                logger.error(
                    "write_connection_error",
                    error=str(e),
                    exc_info=True,
                )
                raise

    @asynccontextmanager
    async def acquire_read(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire a connection for READ operations.
        Uses replica if available, falls back to primary.
        """
        pool = self.read_pool if self._replica_available and self.read_pool else self.write_pool
        
        if not pool:
            raise RuntimeError("No database pool available for reads")

        async with pool.acquire() as conn:
            try:
                yield conn
            except Exception as e:
                # If replica fails, try primary
                if pool == self.read_pool and self.write_pool:
                    logger.warning(
                        "read_replica_failed_fallback_to_primary",
                        error=str(e),
                    )
                    self._replica_available = False
                    async with self.write_pool.acquire() as fallback_conn:
                        yield fallback_conn
                else:
                    logger.error(
                        "read_connection_error",
                        error=str(e),
                        exc_info=True,
                    )
                    raise

    async def check_replica_health(self) -> bool:
        """
        Check if replica is healthy and re-enable if it was disabled.
        Called periodically to restore replica usage after failures.
        """
        if self._replica_available:
            return True
            
        if not self.read_pool:
            return False
            
        try:
            async with self.read_pool.acquire() as conn:
                is_replica = await conn.fetchval("SELECT pg_is_in_recovery()")
                if is_replica:
                    self._replica_available = True
                    logger.info("read_replica_restored")
                    return True
        except Exception as e:
            logger.debug("replica_health_check_failed", error=str(e))
            
        return False

    @property
    def replica_available(self) -> bool:
        """Check if replica is currently being used for reads"""
        return self._replica_available


# Global pool manager instance
pool_manager = DatabasePoolManager()


async def init_db_pools() -> None:
    """Initialize database pools - call during app startup"""
    await pool_manager.init_pools()


async def close_db_pools() -> None:
    """Close database pools - call during app shutdown"""
    await pool_manager.close_pools()


async def get_db_write() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency for WRITE operations.
    Use this for INSERT, UPDATE, DELETE, and any data modifications.
    
    Example:
        @router.post("/items")
        async def create_item(db: asyncpg.Connection = Depends(get_db_write)):
            await db.execute("INSERT INTO items ...")
    """
    async with pool_manager.acquire_write() as conn:
        yield conn


async def get_db_read() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency for READ operations.
    Use this for SELECT queries and read-only operations.
    
    Example:
        @router.get("/items")
        async def list_items(db: asyncpg.Connection = Depends(get_db_read)):
            return await db.fetch("SELECT * FROM items")
    """
    async with pool_manager.acquire_read() as conn:
        yield conn


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Legacy dependency - routes to WRITE pool for backward compatibility.
    New code should use get_db_write() or get_db_read() explicitly.
    """
    async with pool_manager.acquire_write() as conn:
        yield conn
