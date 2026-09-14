"""enable_pgvector_extension

Revision ID: 000000000001
Revises: 
Create Date: 2026-09-03 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '000000000001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    # Do not cascade drop extension to avoid destroying dependent vector columns/tables
    op.execute("DROP EXTENSION IF EXISTS vector;")
