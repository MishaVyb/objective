from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from objective.db.base import Base, BaseModelFieldsMixin
from objective.db.models.users import UserModel


class ProjectModel(Base, BaseModelFieldsMixin):
    __tablename__ = "project"

    # base:
    # id: Mapped[uuid.UUID] = mapped_column(
    #     primary_key=True,
    #     server_default=func.uuid_generate_v4(),
    # )
    # created_at: Mapped[datetime] = mapped_column(
    #     server_default=func.current_timestamp(),
    # )
    # is_deleted: Mapped[bool] = mapped_column(default=False)
    # """Supports deleting for client, but archive on backend. """

    # meta info:
    name: Mapped[str | None]

    # relations:
    user: Mapped[UserModel] = relationship("UserModel", back_populates="projects")
    # user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))

    scenes: Mapped[SceneModel] = relationship("SceneModel", back_populates="project")


class SceneModel(Base, BaseModelFieldsMixin):
    __tablename__ = "scene"

    # base:
    # id: Mapped[uuid.UUID] = mapped_column(
    #     primary_key=True,
    #     server_default=func.uuid_generate_v4(),
    # )
    # created_at: Mapped[datetime] = mapped_column(
    #     server_default=func.current_timestamp(),
    # )
    # updated_at: Mapped[datetime | None] = mapped_column(
    #     onupdate=func.current_timestamp()
    # )
    # """Resolve simultaneously updates. """
    # updated_by: Mapped[datetime | None]
    # """Supports collab mode. """
    # is_deleted: Mapped[bool] = mapped_column(default=False)
    # """Supports deleting for client, but archive on backend. """

    # relations:
    user: Mapped[UserModel] = relationship("UserModel", back_populates="scenes")
    # user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    project: Mapped[ProjectModel] = relationship(
        "ProjectModel",
        back_populates="scenes",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project.id"))

    # meta info:
    name: Mapped[str | None]
    ...

    # scene data:
    type: Mapped[str]
    version: Mapped[int]
    source: Mapped[str]  # app url
    elements: Mapped[list]
    app_state: Mapped[dict]

    # relations:
    files: Mapped[list[FileModel]] = relationship("FileModel", back_populates="scene")


class FileModel(Base, BaseModelFieldsMixin):
    __tablename__ = "file"
    __table_args__ = (UniqueConstraint("scene_id", "file_id"),)

    # base:
    # id: Mapped[uuid.UUID] = mapped_column(
    #     primary_key=True,
    #     server_default=func.uuid_generate_v4(),
    # )

    # file data
    file_id: Mapped[str] = mapped_column(index=True)  # excalidraw(!) file id
    type: Mapped[str]
    data: Mapped[str]

    # relations:
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scene.id"))
    scene: Mapped[SceneModel] = relationship("SceneModel", back_populates="files")


# Postponed relations definition
# https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#adding-relationships-to-mapped-classes-after-declaration
UserModel.projects = relationship("ProjectModel", back_populates="user")
UserModel.scenes = relationship("SceneModel", back_populates="user")
