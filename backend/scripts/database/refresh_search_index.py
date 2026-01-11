"""
Setup materialized view refresh using pg_cron

Usage:
    docker compose exec backend \
        python -m app.scripts.database.refresh_search_index
"""
import asyncio
import ssl
from contextlib import asynccontextmanager

import asyncpg

from app.config import settings


@asynccontextmanager
async def get_conn():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    conn = await asyncpg.connect(
        dsn=settings.alembic_database_url,
        ssl=ssl_context,
        timeout=30,
    )
    try:
        yield conn
    finally:
        await conn.close()


async def setup_cron_refresh() -> None:
    async with get_conn() as conn:
        # pg_cron must be installed once per DB
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")

        # Ensure schema resolution is deterministic
        await conn.execute("SET search_path = proveo")

        # Remove existing job if present
        await conn.execute(
            """
            SELECT cron.unschedule('refresh-company-search')
            WHERE EXISTS (
                SELECT 1
                FROM cron.job
                WHERE jobname = 'refresh-company-search'
            )
            """
        )

        # Schedule every 15 minutes
        await conn.execute(
            """
            SELECT cron.schedule(
                'refresh-company-search',
                '* * * * *',
                $$
                SET search_path = proveo, public;
                REFRESH MATERIALIZED VIEW CONCURRENTLY company_search;
                $$
            )
            """
        )

        print("Cron job scheduled: refresh every 15 minutes")


if __name__ == "__main__":
    asyncio.run(setup_cron_refresh())
