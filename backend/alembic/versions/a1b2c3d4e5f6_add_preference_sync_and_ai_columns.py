"""add_preference_sync_and_ai_columns

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-09-12 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('preferences', sa.Column('sync_interval_hours', sa.Integer(), nullable=False, server_default='24'))
    op.add_column('preferences', sa.Column('auto_sync_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('preferences', sa.Column('last_auto_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('preferences', sa.Column('ai_provider', sa.String(length=100), nullable=True))
    op.add_column('preferences', sa.Column('ai_model', sa.String(length=100), nullable=True))
    op.add_column('preferences', sa.Column('ai_base_url', sa.String(length=500), nullable=True))
    op.add_column('preferences', sa.Column('ai_api_key', sa.String(length=500), nullable=True))
    op.add_column('preferences', sa.Column('setup_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('preferences', 'setup_completed')
    op.drop_column('preferences', 'ai_api_key')
    op.drop_column('preferences', 'ai_base_url')
    op.drop_column('preferences', 'ai_model')
    op.drop_column('preferences', 'ai_provider')
    op.drop_column('preferences', 'last_auto_sync_at')
    op.drop_column('preferences', 'auto_sync_enabled')
    op.drop_column('preferences', 'sync_interval_hours')
