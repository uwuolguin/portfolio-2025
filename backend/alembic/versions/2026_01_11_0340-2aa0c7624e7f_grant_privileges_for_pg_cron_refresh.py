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
    # Create pg_cron extension
    op.execute("""
        CREATE EXTENSION IF NOT EXISTS pg_cron;
    """)

    # Schedule pg_cron job to run as postgres user
    op.execute("""
        SELECT cron.schedule(
            'refresh_company_search',
            '* * * * *',
            $$REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search$$
        );
    """)


def downgrade():
    # Unschedule the cron job
    op.execute("""
        SELECT cron.unschedule('refresh_company_search');
    """)
