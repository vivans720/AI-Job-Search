"""create_agent_activity_tables

Revision ID: d4e5f6a7b8c9
Revises: a7b8c9d0e1f2
Create Date: 2026-09-20 02:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('trigger', sa.String(length=50), nullable=False, server_default='chat'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('metrics', JSONB, server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_agent_runs_user_id', 'agent_runs', ['user_id'])
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'])
    op.create_index('ix_agent_runs_created_at', 'agent_runs', ['created_at'])
    op.create_index('idx_agent_runs_user_created', 'agent_runs', ['user_id', sa.text('created_at DESC')])

    op.create_table(
        'agent_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', UUID(as_uuid=True), sa.ForeignKey('agent_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=True),
        sa.Column('action_summary', sa.Text(), nullable=False),
        sa.Column('payload', JSONB, server_default='{}', nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_events_run_id', 'agent_events', ['run_id'])
    op.create_index('ix_agent_events_event_type', 'agent_events', ['event_type'])
    op.create_index('ix_agent_events_created_at', 'agent_events', ['created_at'])
    op.create_index('idx_agent_events_run_created', 'agent_events', ['run_id', sa.text('created_at ASC')])


def downgrade() -> None:
    op.drop_index('idx_agent_events_run_created', table_name='agent_events')
    op.drop_index('ix_agent_events_created_at', table_name='agent_events')
    op.drop_index('ix_agent_events_event_type', table_name='agent_events')
    op.drop_index('ix_agent_events_run_id', table_name='agent_events')
    op.drop_table('agent_events')

    op.drop_index('idx_agent_runs_user_created', table_name='agent_runs')
    op.drop_index('ix_agent_runs_created_at', table_name='agent_runs')
    op.drop_index('ix_agent_runs_status', table_name='agent_runs')
    op.drop_index('ix_agent_runs_user_id', table_name='agent_runs')
    op.drop_table('agent_runs')
