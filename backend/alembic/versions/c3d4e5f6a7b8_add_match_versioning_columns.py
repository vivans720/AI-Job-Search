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
    op.add_column('matches', sa.Column('algorithm_version', sa.String(length=32), nullable=True))
    op.add_column('matches', sa.Column('profile_version', sa.String(length=64), nullable=True))
    op.add_column('matches', sa.Column('preference_version', sa.String(length=64), nullable=True))
    op.add_column('matches', sa.Column('job_version', sa.String(length=64), nullable=True))

    op.create_index(op.f('ix_matches_algorithm_version'), 'matches', ['algorithm_version'], unique=False)
    op.create_index(op.f('ix_matches_profile_version'), 'matches', ['profile_version'], unique=False)
    op.create_index(op.f('ix_matches_preference_version'), 'matches', ['preference_version'], unique=False)
    op.create_index(op.f('ix_matches_job_version'), 'matches', ['job_version'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_matches_job_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_preference_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_profile_version'), table_name='matches')
    op.drop_index(op.f('ix_matches_algorithm_version'), table_name='matches')

    op.drop_column('matches', 'job_version')
    op.drop_column('matches', 'preference_version')
    op.drop_column('matches', 'profile_version')
    op.drop_column('matches', 'algorithm_version')
