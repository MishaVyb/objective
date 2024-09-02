from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import DeclarativeFieldsMixin
from .users import User


class Project(DeclarativeFieldsMixin):
    name: Mapped[str | None]

    # relations:
    scenes: Mapped[list[Scene]] = relationship(
        "Scene",
        back_populates="project",
        order_by="Scene.created_at",
    )


class Scene(DeclarativeFieldsMixin):
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="scenes",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"))

    # meta info:
    name: Mapped[str]

    # scene data:
    type: Mapped[str | None]
    version: Mapped[int | None]
    source: Mapped[str | None]  # app url
    elements: Mapped[list] = mapped_column(default=[])
    app_state: Mapped[dict] = mapped_column(default={})

    # relations:
    files: Mapped[list[File]] = relationship(
        "File",
        back_populates="scene",
        order_by="File.created_at",
    )


class File(DeclarativeFieldsMixin):
    __table_args__ = (UniqueConstraint("scene_id", "file_id"),)

    # file data
    file_id: Mapped[str] = mapped_column(index=True)  # excalidraw(!) file id
    type: Mapped[str]
    data: Mapped[str]

    # relations:
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scene.id"))
    scene: Mapped[Scene] = relationship("Scene", back_populates="files")


# Postponed relations definition
# https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#adding-relationships-to-mapped-classes-after-declaration
User.projects = relationship("Project", back_populates="user", uselist=True)
User.scenes = relationship("Scene", back_populates="user", uselist=True)
User.files = relationship("File", back_populates="user", uselist=True)
