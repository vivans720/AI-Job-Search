"""add_company_logo_urls

Revision ID: a7b8c9d0e1f2
Revises: f3a4b5c6d7e8
Create Date: 2026-09-16 00:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('logo_url', sa.String(length=2048), nullable=True))
    op.add_column('jobs', sa.Column('company_logo_url', sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'company_logo_url')
    op.drop_column('companies', 'logo_url')
