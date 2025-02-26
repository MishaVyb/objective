"""add entity access

Revision ID: 7734c456d1a5
Revises: d0101d50d313
Create Date: 2025-02-26 16:29:48.384785

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.schemas import schemas

# revision identifiers, used by Alembic.
revision: str = "7734c456d1a5"
down_revision: Union[str, None] = "d0101d50d313"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "access",
            sa.String(),
            server_default=schemas.Access.PRIVATE,
            nullable=False,
        ),
    )
    op.add_column(
        "scene",
        sa.Column(
            "access",
            sa.String(),
            server_default=schemas.Access.PRIVATE,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("scene", "access")
    op.drop_column("project", "access")
