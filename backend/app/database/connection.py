import ssl
from typing import AsyncGenerator, Optional

import asyncpg
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class DatabasePoolManager:
    write_pool: asyncpg.Pool | None = None

    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def init_pools(self) -> None:
        ssl_context = self._create_ssl_context()
        try:
            self.write_pool = await asyncpg.create_pool(
                dsn=settings.alembic_database_url,
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
                "database_pool_initialized",
                pool_size=self.write_pool.get_size(),
            )

        except Exception as e:
            logger.error(
                "database_pool_init_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        await conn.execute("SET timezone TO 'UTC'")
        await conn.execute(f"SET statement_timeout TO '{settings.db_timeout}s'")
        await conn.execute("SET log_statement_stats TO off")
        await conn.execute("SET pg_trgm.similarity_threshold = 0.3")

        if settings.debug:
            await conn.execute(
                f"SET log_min_duration_statement TO "
                f"{int(settings.db_slow_query_threshold * 1000)}"
            )

    async def close_pools(self) -> None:
        if self.write_pool:
            await self.write_pool.close()
            self.write_pool = None
        logger.info("database_pool_closed")


pool_manager = DatabasePoolManager()


async def init_db_pools() -> None:
    await pool_manager.init_pools()


async def close_db_pools() -> None:
    await pool_manager.close_pools()


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if not pool_manager.write_pool:
        raise RuntimeError("Database pool not initialized")

    async with pool_manager.write_pool.acquire() as conn:
        try:
            yield conn
        except Exception as e:
            logger.error(
                "database_connection_error",
                error=str(e),
                exc_info=True,
            )
            raise