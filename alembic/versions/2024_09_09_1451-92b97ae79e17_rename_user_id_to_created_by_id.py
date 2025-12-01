"""rename user_id to created_by_id and constraints

Revision ID: 92b97ae79e17
Revises: fe157e9d1c30
Create Date: 2024-09-09 14:51:03.478057

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92b97ae79e17"
down_revision: Union[str, None] = "fe157e9d1c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # rename columns
    op.alter_column("file", "user_id", new_column_name="created_by_id")
    op.alter_column("project", "user_id", new_column_name="created_by_id")
    op.alter_column("scene", "user_id", new_column_name="created_by_id")

    op.alter_column("file", "updated_by", new_column_name="updated_by_id")
    op.alter_column("project", "updated_by", new_column_name="updated_by_id")
    op.alter_column("scene", "updated_by", new_column_name="updated_by_id")

    # rename constraints:
    op.drop_constraint("project_user_id_fkey", "project", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_project_created_by_id_user"),
        "project",
        "user",
        ["created_by_id"],
        ["id"],
    )

    op.drop_constraint("scene_user_id_fkey", "scene", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_scene_created_by_id_user"),
        "scene",
        "user",
        ["created_by_id"],
        ["id"],
    )

    op.drop_constraint("file_user_id_fkey", "file", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_file_created_by_id_user"),
        "file",
        "user",
        ["created_by_id"],
        ["id"],
    )

    # create constraints
    op.create_foreign_key(
        op.f("fk_project_updated_by_id_user"),
        "project",
        "user",
        ["updated_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_scene_updated_by_id_user"),
        "scene",
        "user",
        ["updated_by_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_file_updated_by_id_user"),
        "file",
        "user",
        ["updated_by_id"],
        ["id"],
    )

    # indexes (for ForeignKeys)
    op.create_index(
        op.f("ix_file_created_by_id"),
        "file",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_updated_by_id"),
        "file",
        ["updated_by_id"],
        unique=False,
    )
    op.create_index(op.f("ix_file_scene_id"), "file", ["scene_id"], unique=False)
    ##
    op.create_index(
        op.f("ix_project_created_by_id"),
        "project",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_updated_by_id"),
        "project",
        ["updated_by_id"],
        unique=False,
    )
    ##
    op.create_index(
        op.f("ix_scene_created_by_id"),
        "scene",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(op.f("ix_scene_project_id"), "scene", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_scene_updated_by_id"),
        "scene",
        ["updated_by_id"],
        unique=False,
    )

    # not nullable:
    op.alter_column("project", "name", existing_type=sa.VARCHAR(), nullable=False)

    # rename:
    op.drop_constraint("file_scene_id_file_id_key", "file", type_="unique")
    op.create_unique_constraint(
        op.f("uq_file_scene_id"),
        "file",
        ["scene_id", "file_id"],
    )


def downgrade() -> None:

    # rename columns
    op.alter_column("file", "created_by_id", new_column_name="user_id")
    op.alter_column("project", "created_by_id", new_column_name="user_id")
    op.alter_column("scene", "created_by_id", new_column_name="user_id")

    op.alter_column("file", "updated_by_id", new_column_name="updated_by")
    op.alter_column("project", "updated_by_id", new_column_name="updated_by")
    op.alter_column("scene", "updated_by_id", new_column_name="updated_by")
