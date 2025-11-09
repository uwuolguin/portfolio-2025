"""add materialized view

Revision ID: c70f6d3ab4ec
Revises: 28de81bc6b20
Create Date: 2025-09-28 23:45:28.175115
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c70f6d3ab4ec'
down_revision: Union[str, Sequence[str], None] = '28de81bc6b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS proveo.company_search;")
    op.execute("""
    CREATE MATERIALIZED VIEW proveo.company_search AS
    SELECT 
        c.uuid AS company_id,
        c.name AS company_name,
        c.description_es AS company_description_es,
        c.description_en AS company_description_en,
        c.address,
        c.email AS company_email,
        c.phone,
        c.image_url,
        p.name_es AS product_name_es,
        p.name_en AS product_name_en,
        u.name AS user_name,
        u.email AS user_email,
        cm.name AS commune_name,
        -- Full-text search vector for keyword matching
        to_tsvector('spanish',
            coalesce(cast(c.name AS text),'') || ' ' ||
            coalesce(c.description_es,'') || ' ' ||
            coalesce(p.name_es,'') || ' ' ||
            coalesce(cm.name,'') || ' ' ||
            coalesce(u.name,'') || ' ' ||
            coalesce(u.email,'')
        )
        ||
        to_tsvector('english',
            coalesce(c.name,'') || ' ' ||
            coalesce(c.description_en,'') || ' ' ||
            coalesce(p.name_en,'')
        ) AS search_vector,
        -- Concatenated searchable text for LIKE/ILIKE queries
        LOWER(
            coalesce(c.name, '') || ' ' ||
            coalesce(c.description_es, '') || ' ' ||
            coalesce(c.description_en, '') || ' ' ||
            coalesce(p.name_es, '') || ' ' ||
            coalesce(p.name_en, '') || ' ' ||
            coalesce(cm.name, '') || ' ' ||
            coalesce(c.address, '') || ' ' ||
            coalesce(u.name, '')
        ) AS searchable_text
    FROM proveo.companies c
    LEFT JOIN proveo.products p ON p.uuid = c.product_uuid
    LEFT JOIN proveo.users u ON u.uuid = c.user_uuid
    LEFT JOIN proveo.communes cm ON cm.uuid = c.commune_uuid;
    """)

    # 3. Create indexes
    op.execute("""
    CREATE INDEX idx_company_search_vector
    ON proveo.company_search
    USING GIN (search_vector);
    """)

    op.execute("""
    CREATE INDEX idx_company_searchable_text
    ON proveo.company_search
    USING GIN (searchable_text gin_trgm_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS proveo.idx_company_searchable_text;")
    op.execute("DROP INDEX IF EXISTS proveo.idx_company_search_vector;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS proveo.company_search;")