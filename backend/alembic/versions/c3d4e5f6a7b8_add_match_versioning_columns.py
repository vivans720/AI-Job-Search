"""add_match_versioning_columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-14 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        ALTER TABLE matches
        ADD COLUMN IF NOT EXISTS algorithm_version VARCHAR(32),
        ADD COLUMN IF NOT EXISTS profile_version VARCHAR(64),
        ADD COLUMN IF NOT EXISTS preference_version VARCHAR(64),
        ADD COLUMN IF NOT EXISTS job_version VARCHAR(64);
    """))

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_matches_algorithm_version ON matches (algorithm_version);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_matches_profile_version ON matches (profile_version);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_matches_preference_version ON matches (preference_version);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_matches_job_version ON matches (job_version);"))


def downgrade() -> None:
    op.drop_index(op.f('ix_matches_job_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_preference_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_profile_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_algorithm_version'), table_name='matches')

    op.drop_column('matches', 'job_version')
    op.drop_column('matches', 'preference_version')
    op.drop_column('matches', 'profile_version')
    op.drop_column('matches', 'algorithm_version')
