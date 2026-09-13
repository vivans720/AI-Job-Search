"""add_ai_fallback_and_gateway_columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-13 00:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE preferences
        ADD COLUMN IF NOT EXISTS ai_fallback_provider VARCHAR(100),
        ADD COLUMN IF NOT EXISTS ai_fallback_model VARCHAR(100),
        ADD COLUMN IF NOT EXISTS ai_provider_config JSONB;
    """))


def downgrade() -> None:
    op.drop_column('preferences', 'ai_provider_config')
    op.drop_column('preferences', 'ai_fallback_model')
    op.drop_column('preferences', 'ai_fallback_provider')
