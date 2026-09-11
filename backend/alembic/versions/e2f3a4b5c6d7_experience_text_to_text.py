"""experience_text_to_text

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-06 21:37:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('jobs', 'experience_text', existing_type=sa.String(length=255), type_=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column('jobs', 'experience_text', existing_type=sa.Text(), type_=sa.String(length=255), nullable=True)
