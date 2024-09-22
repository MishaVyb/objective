from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import DeclarativeFieldsMixin
from .users import User


class Project(DeclarativeFieldsMixin):
    name: Mapped[str]

    # relations:
    scenes: Mapped[list[Scene]] = relationship(
        "Scene",
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

    elements: Mapped[list] = mapped_column(default=[])
    app_state: Mapped[dict] = mapped_column(default={})


class Element(DeclarativeFieldsMixin):
    pass


class File(DeclarativeFieldsMixin):

    # file data
    file_id: Mapped[str] = mapped_column(
        index=True,
        unique=True,
    )  # excalidraw(!) file id
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
