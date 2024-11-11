"""remove elements col

Revision ID: 2a04a94dceec
Revises: 65a67fe53de9
Create Date: 2024-11-11 11:49:05.967413

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a04a94dceec"
down_revision: Union[str, None] = "65a67fe53de9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TODO
    # run all manual e2e tests against read db
    # and only after that remove elements col
    raise NotImplementedError

    op.drop_column("scene", "elements")


def downgrade() -> None:

    op.add_column(
        "scene",
        sa.Column(
            "elements",
            postgresql.JSON(astext_type=sa.Text()),
            autoincrement=False,
            nullable=False,
        ),
    )
