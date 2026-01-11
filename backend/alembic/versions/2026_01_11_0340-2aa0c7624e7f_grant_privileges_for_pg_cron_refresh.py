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
    op.execute("""
        -- Allow access to the schema
        GRANT USAGE ON SCHEMA proveo TO postgres;

        -- Optional: allow read access
        GRANT SELECT
        ON ALL TABLES IN SCHEMA proveo
        TO postgres;

        ALTER DEFAULT PRIVILEGES IN SCHEMA proveo
        GRANT SELECT ON TABLES TO postgres;

        -- REQUIRED: pg_cron must own the materialized view
        ALTER MATERIALIZED VIEW proveo.your_materialized_view
        OWNER TO postgres;
    """)

def downgrade():
    op.execute("""
        ALTER MATERIALIZED VIEW proveo.your_materialized_view
        OWNER TO user;

        REVOKE SELECT ON ALL TABLES IN SCHEMA proveo FROM postgres;
        REVOKE USAGE ON SCHEMA proveo FROM postgres;
    """)