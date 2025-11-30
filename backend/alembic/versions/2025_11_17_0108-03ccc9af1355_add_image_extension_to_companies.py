"""add_image_extension_to_companies

Revision ID: 03ccc9af1355
Revises: b999848032b2
Create Date: 2025-11-17 01:08:16.910312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03ccc9af1355'
down_revision: Union[str, Sequence[str], None] = '69693d3a80bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'companies',
        sa.Column('image_extension', sa.String(10), nullable=False),
        schema='proveo'
    )
    op.add_column(
        'companies_deleted',
        sa.Column('image_extension', sa.String(10), nullable=False),
        schema='proveo'
    )
    
def downgrade() -> None:
    op.drop_column('companies', 'image_extension', schema='proveo')
    op.drop_column('companies_deleted', 'image_extension', schema='proveo')