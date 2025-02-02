"""add elements table

Revision ID: d1ce0fb7ac9a
Revises: 92b97ae79e17
Create Date: 2024-09-30 10:23:55.832501

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1ce0fb7ac9a"
down_revision: Union[str, None] = "92b97ae79e17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "element",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("updated", sa.Float(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("version_nonce", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("_json", sa.JSON(), nullable=False),
        sa.Column("_updated", sa.Float(), nullable=False),
        sa.Column("_scene_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["_scene_id"],
            ["scene.id"],
            name=op.f("fk_element__scene_id_scene"),
        ),
        sa.PrimaryKeyConstraint("_scene_id", "id", name=op.f("pk_element")),
    )
    op.create_index(
        op.f("ix_element__scene_id"),
        "element",
        ["_scene_id"],
        unique=False,
    )

    # projects
    op.create_index(
        op.f("ix_project_created_at"),
        "project",
        ["created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_scene_created_at"), "scene", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scene_created_at"), table_name="scene")
    op.drop_index(op.f("ix_project_created_at"), table_name="project")
    op.drop_index(op.f("ix_element__scene_id"), table_name="element")
    op.drop_table("element")
