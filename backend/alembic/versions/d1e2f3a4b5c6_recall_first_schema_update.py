"""recall_first_schema_update

Revision ID: d1e2f3a4b5c6
Revises: 277d46cb26d2
Create Date: 2026-09-06 20:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = '277d46cb26d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make experience_min and experience_max nullable
    op.alter_column('jobs', 'experience_min', existing_type=sa.Integer(), nullable=True)
    op.alter_column('jobs', 'experience_max', existing_type=sa.Integer(), nullable=True)

    # Add experience_text, experience_confidence, description_confidence
    op.add_column('jobs', sa.Column('experience_text', sa.String(length=255), nullable=True))
    op.add_column('jobs', sa.Column('experience_confidence', sa.String(length=20), server_default='LOW', nullable=False))
    op.add_column('jobs', sa.Column('description_confidence', sa.String(length=20), server_default='HIGH', nullable=False))


def downgrade() -> None:
    op.drop_column('jobs', 'description_confidence')
    op.drop_column('jobs', 'experience_confidence')
    op.drop_column('jobs', 'experience_text')
    op.alter_column('jobs', 'experience_max', existing_type=sa.Integer(), nullable=False, server_default='0')
    op.alter_column('jobs', 'experience_min', existing_type=sa.Integer(), nullable=False, server_default='0')
