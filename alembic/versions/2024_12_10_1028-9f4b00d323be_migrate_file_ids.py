"""migrate file ids

Revision ID: 9f4b00d323be
Revises: 4dff8c1ba9a2
Create Date: 2024-12-10 10:28:00.551377

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "9f4b00d323be"
down_revision: Union[str, None] = "4dff8c1ba9a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # files
    op.alter_column(
        "file",
        "id",
        existing_type=sa.UUID(),
        type_=sa.String(),
        existing_nullable=False,
        existing_server_default=sa.text("uuid_generate_v4()"),  # type: ignore
    )
    op.drop_index("ix_file_file_id", table_name="file")
    op.drop_index("ix_file_scene_id", table_name="file")
    op.drop_constraint("uq_file_scene_id", "file", type_="unique")
    op.create_index(op.f("ix_file_created_at"), "file", ["created_at"], unique=False)
    op.create_index(op.f("ix_file_id"), "file", ["id"], unique=True)
    op.drop_column("file", "scene_id")

    # migrate file ids
    # op.execute(sa.text("UPDATE file SET id = file_id;"))
    connection = op.get_bind()

    with Session(connection) as session, session.begin():
        files = session.execute(
            sa.text("SELECT file.id, file.file_id FROM file"),
        ).all()

        file_ids = {f.file_id: f for f in files}
        logger.info(
            "Migrate file ids: %s. Skip duplicates: %s ",
            len(file_ids),
            len(files) - len(file_ids),
        )

        for pg_id, file_id in file_ids.values():
            logger.info("Migrate file id. %s", file_id)
            op.execute(sa.text(f"UPDATE file SET id = file_id WHERE id = '{pg_id}';"))

        logger.info("Commit session. ")
        session.commit()

    op.drop_column("file", "file_id")


def downgrade() -> None:
    op.add_column(
        "file",
        sa.Column("file_id", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "file",
        sa.Column("scene_id", sa.UUID(), autoincrement=False, nullable=True),
    )
    op.drop_index(op.f("ix_file_id"), table_name="file")
    op.drop_index(op.f("ix_file_created_at"), table_name="file")
    op.create_unique_constraint("uq_file_scene_id", "file", ["scene_id", "file_id"])
    op.create_index("ix_file_scene_id", "file", ["scene_id"], unique=False)
    op.create_index("ix_file_file_id", "file", ["file_id"], unique=False)

    # WARNING disable those downgrade migrations...
    # op.alter_column(
    #     "file",
    #     "id",
    #     existing_type=sa.String(),
    #     type_=sa.UUID(),
    #     existing_nullable=False,
    #     existing_server_default=sa.text("uuid_generate_v4()"),
    # )
