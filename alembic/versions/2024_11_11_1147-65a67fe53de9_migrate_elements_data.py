"""migrate_elements_data

Revision ID: 65a67fe53de9
Revises: d1ce0fb7ac9a
Create Date: 2024-11-11 11:47:51.892049

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op
from app.repository import models
from app.schemas import schemas

logger = logging.getLogger("alembic.runtime.migration")


# revision identifiers, used by Alembic.
revision: str = "65a67fe53de9"
down_revision: Union[str, None] = "d1ce0fb7ac9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    with Session(connection) as session, session.begin():
        session.execute(sa.text("DELETE FROM element"))

        scenes = session.execute(
            sa.text("SELECT scene.name, scene.id, scene.elements FROM scene"),
        ).all()

        logger.info("Migrate elements for %s scenes. ", len(scenes))
        for name, scene_id, elements in scenes:
            if not elements:
                continue

            logger.info("Migrate '%s' scene elements. %s", name, scene_id)
            instances = []
            for el in elements:
                el = schemas.Element.model_validate(el)
                instance = models.Element(
                    id=el.id,
                    updated=el.updated,
                    version=el.version,
                    version_nonce=el.version_nonce,
                    #
                    # image el props
                    file_id=el.file_id,
                    status=el.status,
                    #
                    # Database only values
                    _json=el.model_dump(exclude_unset=True),
                    _scene_id=scene_id,
                )
                session.add(instance)
                instances.append(instance)

            logger.info("Flush %s elements. ", len(instances))
            session.flush(instances)

        logger.info("Commit session. ")
        session.commit()


def downgrade() -> None:
    pass
