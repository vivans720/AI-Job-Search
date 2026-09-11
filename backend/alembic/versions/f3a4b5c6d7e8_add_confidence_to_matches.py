"""add_confidence_to_matches

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-12 02:48:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matches', sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('matches', sa.Column('confidence_label', sa.String(length=20), nullable=False, server_default='HIGH'))


def downgrade() -> None:
    op.drop_column('matches', 'confidence_label')
    op.drop_column('matches', 'confidence')
