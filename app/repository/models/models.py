from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.schemas import ElementID, FileID

from .base import DeclarativeFieldsMixin
from .users import User


class Project(DeclarativeFieldsMixin):
    name: Mapped[str]

    # relations:
    scenes: Mapped[list[Scene]] = relationship(
        back_populates="project",
        order_by="Scene.created_at",
    )


class Scene(DeclarativeFieldsMixin):
    project: Mapped[Project] = relationship(Project, back_populates="scenes")
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(Project.id), index=True)

    # objective scene meta info
    name: Mapped[str]

    # excalidraw scene data:
    type: Mapped[str | None]
    version: Mapped[int | None]
    source: Mapped[str | None]  # app url

    app_state: Mapped[dict] = mapped_column(default={})
    elements: Mapped[list[Element]] = relationship(
        # ??? only not deleted elements for first initial scene loading...
    )


class Element(DeclarativeFieldsMixin):

    # Excalidraw
    # id -- cannot be primary_key as it's uniq only per scene
    id: Mapped[ElementID] = mapped_column()
    json: Mapped[dict]

    # Meta for synchronization (resolve merging conflicts)
    version: Mapped[int]
    version_nonce: Mapped[int]
    updated: Mapped[int]

    # ExcalidrawImageElement props
    file_id: Mapped[str | None]
    status: Mapped[str | None]

    # pg_id = mapped_column(
    #     primary_key=True,
    #     default=lambda: uuid.uuid4(),
    # )
    scene_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Scene.id),
        index=True,
    )
    __table_args__ = (
        #
        PrimaryKeyConstraint(scene_id, id),
    )


class File(DeclarativeFieldsMixin):
    id: Mapped[FileID] = mapped_column(primary_key=True, index=True, unique=True)
    type: Mapped[str]
    data: Mapped[str]  # VARCHAR ~ Postgres TEXT -- unlimited length (but up to 1gb)


# Postponed relations definition
# https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#adding-relationships-to-mapped-classes-after-declaration
User.projects = relationship(
    Project,
    back_populates="created_by",
    uselist=True,
    foreign_keys=[Project.created_by_id],
)
User.scenes = relationship(
    Scene,
    back_populates="created_by",
    uselist=True,
    foreign_keys=[Scene.created_by_id],
)
User.files = relationship(
    File,
    back_populates="created_by",
    uselist=True,
    foreign_keys=[File.created_by_id],
)
