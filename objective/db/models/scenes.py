from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)

from objective.db.base import Base
from objective.db.models.users import UserModel

if TYPE_CHECKING:
    _TBase = DeclarativeBase
else:
    _TBase = object


class BaseFieldsMixin(_TBase):
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=datetime.now)
    """Resolve simultaneously updates. """
    updated_by: Mapped[uuid.UUID | None]
    """Supports collab mode. """
    is_deleted: Mapped[bool] = mapped_column(default=False)
    """Supports deleting for client, but archive on backend. """

    # relations:
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))  # TODO created_by

    @declared_attr
    def user(cls) -> Mapped[UserModel]:
        return relationship("UserModel")

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower().replace("model", "")


class ProjectModel(Base, BaseFieldsMixin):
    name: Mapped[str | None]

    # relations:
    scenes: Mapped[list[SceneModel]] = relationship(
        "SceneModel",
        back_populates="project",
    )


class SceneModel(Base, BaseFieldsMixin):
    project: Mapped[ProjectModel] = relationship(
        "ProjectModel",
        back_populates="scenes",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"))

    # meta info:
    name: Mapped[str]
    ...

    # scene data:
    type: Mapped[str | None]
    version: Mapped[int | None]
    source: Mapped[str | None]  # app url
    elements: Mapped[list] = mapped_column(default=[])
    app_state: Mapped[dict] = mapped_column(default={})

    # relations:
    files: Mapped[list[FileModel]] = relationship("FileModel", back_populates="scene")


class FileModel(Base, BaseFieldsMixin):
    __table_args__ = (UniqueConstraint("scene_id", "file_id"),)

    # file data
    file_id: Mapped[str] = mapped_column(index=True)  # excalidraw(!) file id
    type: Mapped[str]
    data: Mapped[str]

    # relations:
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scene.id"))
    scene: Mapped[SceneModel] = relationship("SceneModel", back_populates="files")


# Postponed relations definition
# https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#adding-relationships-to-mapped-classes-after-declaration
UserModel.projects = relationship("ProjectModel", back_populates="user", uselist=True)
UserModel.scenes = relationship("SceneModel", back_populates="user", uselist=True)
UserModel.files = relationship("FileModel", back_populates="user", uselist=True)
