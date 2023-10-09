from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from objective.db.base import Base

if TYPE_CHECKING:
    from objective.db.models.users import UserModel


class ProjectModel(Base):
    __tablename__ = "project"

    # base:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.current_timestamp())
    """Resolve simultaneously updates. """
    ubdated_by: Mapped[datetime]
    """Supports collab mode. """
    is_deleted: Mapped[bool] = mapped_column(default=False)
    """Sopports deleting for client, but archive on backend. """

    # meta info:
    name: Mapped[str | None]

    # relations:
    user: Mapped[UserModel] = relationship("UserModel", back_populates="scenes")
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    scenes: Mapped[SceneModel] = relationship("SceneModel", back_populates="project")


class SceneModel(Base):
    __tablename__ = "scene"

    # base:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.current_timestamp())
    """Resolve simultaneously updates. """
    ubdated_by: Mapped[datetime]
    """Supports collab mode. """
    is_deleted: Mapped[bool] = mapped_column(default=False)
    """Sopports deleting for client, but archive on backend. """

    # relations:
    user: Mapped[UserModel] = relationship("UserModel", back_populates="scenes")
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
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


class FileModel(Base):
    __tablename__ = "file"
    __table_args__ = (UniqueConstraint("scene_id", "file_id"),)

    # base:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )

    # file data
    file_id: Mapped[str] = mapped_column(index=True)  # client file id
    type: Mapped[str]
    data: Mapped[str]

    # relations:
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    scene: Mapped[SceneModel] = relationship("Scene", back_populates="files")
