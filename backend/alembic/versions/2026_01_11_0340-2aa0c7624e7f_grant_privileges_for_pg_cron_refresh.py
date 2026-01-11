"""grant privileges for pg_cron refresh

Revision ID: 2aa0c7624e7f
Revises: 03ccc9af1355
Create Date: 2026-01-11 03:40:01.352044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2aa0c7624e7f'
down_revision: Union[str, Sequence[str], None] = '03ccc9af1355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1️⃣ Make sure the schema is accessible
    op.execute("""
        GRANT USAGE ON SCHEMA proveo TO postgres;
    """)

    # 2️⃣ Give read privileges on all tables
    op.execute("""
        GRANT SELECT ON ALL TABLES IN SCHEMA proveo TO postgres;
    """)

    # 3️⃣ Set default privileges for future tables
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA proveo
        GRANT SELECT ON TABLES TO postgres;
    """)

    # 4️⃣ Ensure the materialized view exists and is owned by postgres
    op.execute("""
        ALTER MATERIALIZED VIEW proveo.company_search OWNER TO postgres;
    """)

    # 5️⃣ Schedule pg_cron job to refresh the materialized view every 15 minutes
    op.execute("""
        SELECT cron.schedule(
            'refresh_company_search',
            '*/15 * * * *',
            $$SET search_path = proveo, public; REFRESH MATERIALIZED VIEW CONCURRENTLY company_search$$
        );
    """)


def downgrade():
    # Remove the cron job
    op.execute("""
        SELECT cron.unschedule('refresh_company_search');
    """)