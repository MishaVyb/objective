"""scene elements nullable

Revision ID: 4dff8c1ba9a2
Revises: 65a67fe53de9
Create Date: 2024-11-20 16:24:50.436406

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4dff8c1ba9a2"
down_revision: Union[str, None] = "65a67fe53de9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("scene", "elements", existing_type=sa.JSON(), nullable=True)


def downgrade() -> None:
    pass
