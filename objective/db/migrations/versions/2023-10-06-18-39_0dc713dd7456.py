"""add uuid ext

Revision ID: 0dc713dd7456
Revises: c26aad740747
Create Date: 2023-10-06 18:39:54.750114

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0dc713dd7456"
down_revision = "c26aad740747"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))


def downgrade() -> None:
    op.execute(sa.text('DROP EXTENSION IF EXISTS "uuid-ossp"'))
