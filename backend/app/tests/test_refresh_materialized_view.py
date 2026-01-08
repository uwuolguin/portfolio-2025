"""
Test for materialized view refresh functionality.
Run with: pytest app/tests/test_refresh_materialized_view.py -v

Tests that the company_search materialized view can be refreshed
and reflects data from the companies table.
"""
import pytest
import pytest_asyncio
import asyncpg
import ssl
from contextlib import asynccontextmanager

# Import settings - adjust path if running outside container
import sys
sys.path.insert(0, '/app')
from app.config import settings


@asynccontextmanager
async def get_conn():
    """Get database connection with SSL"""
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


@pytest.mark.asyncio
async def test_refresh_materialized_view():
    """
    Test that the company_search materialized view can be refreshed
    and contains data matching the companies table.
    """
    async with get_conn() as conn:
        # 1. Get count from companies table
        companies_count = await conn.fetchval(
            "SELECT COUNT(*) FROM proveo.companies"
        )
        
        # 2. Refresh the materialized view
        await conn.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search"
        )
        
        # 3. Get count from materialized view
        mv_count = await conn.fetchval(
            "SELECT COUNT(*) FROM proveo.company_search"
        )
        
        # 4. Assert counts match
        assert companies_count == mv_count, (
            f"Materialized view count ({mv_count}) doesn't match "
            f"companies table count ({companies_count})"
        )
        
        # 5. Verify the view has expected columns using pg_attribute
        # (information_schema.columns doesn't include materialized views)
        columns = await conn.fetch("""
            SELECT a.attname as column_name
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE n.nspname = 'proveo'
            AND c.relname = 'company_search'
            AND a.attnum > 0
            AND NOT a.attisdropped
        """)
        column_names = {row['column_name'] for row in columns}
        
        expected_columns = {
            'company_id', 'company_name', 'searchable_text',
            'product_name_es', 'product_name_en', 'commune_name'
        }
        
        assert expected_columns.issubset(column_names), (
            f"Missing expected columns. Found: {column_names}"
        )
        
        print(f"✓ Materialized view refreshed successfully")
        print(f"  Companies count: {companies_count}")
        print(f"  View count: {mv_count}")
        print(f"  Columns: {column_names}")