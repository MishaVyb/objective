"""add file_to_scene table

Revision ID: d0101d50d313
Revises: 9f4b00d323be
Create Date: 2025-02-09 15:58:53.348496

"""

from typing import Sequence, Union

import fastapi_users_db_sqlalchemy
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0101d50d313"
down_revision: Union[str, None] = "9f4b00d323be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "file_to_scene_association",
        sa.Column("scene_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            fastapi_users_db_sqlalchemy.generics.GUID(),
            nullable=False,
        ),
        sa.Column(
            "updated_by_id",
            fastapi_users_db_sqlalchemy.generics.GUID(),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
            name=op.f("fk_file_to_scene_association_created_by_id_user"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file.id"],
            name=op.f("fk_file_to_scene_association_file_id_file"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scene_id"],
            ["scene.id"],
            name=op.f("fk_file_to_scene_association_scene_id_scene"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["user.id"],
            name=op.f("fk_file_to_scene_association_updated_by_id_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_to_scene_association")),
        sa.UniqueConstraint(
            "scene_id",
            "file_id",
            name=op.f("uq_file_to_scene_association_scene_id"),
        ),
    )
    op.create_index(
        op.f("ix_file_to_scene_association_created_at"),
        "file_to_scene_association",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_to_scene_association_created_by_id"),
        "file_to_scene_association",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_to_scene_association_file_id"),
        "file_to_scene_association",
        ["file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_to_scene_association_scene_id"),
        "file_to_scene_association",
        ["scene_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_to_scene_association_updated_by_id"),
        "file_to_scene_association",
        ["updated_by_id"],
        unique=False,
    )
    op.add_column(
        "file",
        sa.Column("kind", sa.String(), server_default="image", nullable=False),
    )
    op.add_column("file", sa.Column("width", sa.Float(), nullable=True))
    op.add_column("file", sa.Column("height", sa.Float(), nullable=True))


def downgrade() -> None:

    op.drop_column("file", "height")
    op.drop_column("file", "width")
    op.drop_column("file", "kind")
    op.drop_index(
        op.f("ix_file_to_scene_association_updated_by_id"),
        table_name="file_to_scene_association",
    )
    op.drop_index(
        op.f("ix_file_to_scene_association_scene_id"),
        table_name="file_to_scene_association",
    )
    op.drop_index(
        op.f("ix_file_to_scene_association_file_id"),
        table_name="file_to_scene_association",
    )
    op.drop_index(
        op.f("ix_file_to_scene_association_created_by_id"),
        table_name="file_to_scene_association",
    )
    op.drop_index(
        op.f("ix_file_to_scene_association_created_at"),
        table_name="file_to_scene_association",
    )
    op.drop_table("file_to_scene_association")
