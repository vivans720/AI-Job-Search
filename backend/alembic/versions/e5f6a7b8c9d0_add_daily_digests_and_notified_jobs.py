"""add daily digests and digest notified jobs tables

Revision ID: e5f6a7b8c9d0
Revises: 155c3c720996
Create Date: 2026-09-20 17:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = '155c3c720996'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'daily_digests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('digest_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('job_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('total_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('strong_matches_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DELIVERED'),
        sa.Column('metadata_info', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_digests_digest_date'), 'daily_digests', ['digest_date'], unique=False)
    op.create_index(op.f('ix_daily_digests_run_id'), 'daily_digests', ['run_id'], unique=False)
    op.create_index(op.f('ix_daily_digests_status'), 'daily_digests', ['status'], unique=False)
    op.create_index(op.f('ix_daily_digests_user_id'), 'daily_digests', ['user_id'], unique=False)

    op.create_table(
        'digest_notified_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('digest_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['digest_id'], ['daily_digests.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'job_id', name='uq_user_job_digest_notified')
    )
    op.create_index(op.f('ix_digest_notified_jobs_digest_id'), 'digest_notified_jobs', ['digest_id'], unique=False)
    op.create_index(op.f('ix_digest_notified_jobs_job_id'), 'digest_notified_jobs', ['job_id'], unique=False)
    op.create_index(op.f('ix_digest_notified_jobs_notified_at'), 'digest_notified_jobs', ['notified_at'], unique=False)
    op.create_index(op.f('ix_digest_notified_jobs_user_id'), 'digest_notified_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_digest_notified_jobs_user_id'), table_name='digest_notified_jobs')
    op.drop_index(op.f('ix_digest_notified_jobs_notified_at'), table_name='digest_notified_jobs')
    op.drop_index(op.f('ix_digest_notified_jobs_job_id'), table_name='digest_notified_jobs')
    op.drop_index(op.f('ix_digest_notified_jobs_digest_id'), table_name='digest_notified_jobs')
    op.drop_table('digest_notified_jobs')

    op.drop_index(op.f('ix_daily_digests_user_id'), table_name='daily_digests')
    op.drop_index(op.f('ix_daily_digests_status'), table_name='daily_digests')
    op.drop_index(op.f('ix_daily_digests_run_id'), table_name='daily_digests')
    op.drop_index(op.f('ix_daily_digests_digest_date'), table_name='daily_digests')
    op.drop_table('daily_digests')
