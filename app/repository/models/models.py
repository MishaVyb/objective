from __future__ import annotations

import time
import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.exc import DetachedInstanceError

from app.repository import schemas
from app.schemas.schemas import ElementID, FileID

from .base import Base, DeclarativeFieldsMixin
from .users import User


class Project(DeclarativeFieldsMixin):
    name: Mapped[str]
    access: Mapped[str] = mapped_column(server_default=schemas.Access.PRIVATE)

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
    access: Mapped[str] = mapped_column(server_default=schemas.Access.PRIVATE)

    # renders (thumbnails/export), not user images:
    files: Mapped[list[File]] = relationship(
        secondary=lambda: FileToSceneAssociation.__table__,
        viewonly=True,
        order_by=lambda: FileToSceneAssociation.id,
    )

    # excalidraw scene data:
    type: Mapped[str | None]
    version: Mapped[int | None]
    source: Mapped[str | None]  # app url

    app_state: Mapped[dict] = mapped_column(default={})
    elements: Mapped[list[Element]] = relationship()


class Element(Base):
    # Excalidraw Element values (client values)
    id: Mapped[ElementID] = mapped_column()  # uniq per scene_id
    updated: Mapped[float]  # UNUSED # client ts
    version: Mapped[int]  # UNUSED # client version
    version_nonce: Mapped[int]  # like 'etag'

    # image el props
    file_id: Mapped[str | None]
    status: Mapped[str | None]

    # Database only values
    _json: Mapped[dict]  # all element data received from client as it is
    _updated: Mapped[float] = mapped_column(  # using service _updated ts, not client
        default=lambda: time.time(),
        onupdate=lambda: time.time(),
    )
    _scene_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Scene.id),
        index=True,
    )
    __table_args__ = (
        #
        PrimaryKeyConstraint(_scene_id, id),
    )

    def __repr__(self):
        try:
            return f"<{self.__class__.__name__}({self.id=}, {self._scene_id=}, {self._updated=})>"
        except DetachedInstanceError:
            return f"<{self.__class__.__name__}(detached)>"


class File(DeclarativeFieldsMixin):
    id: Mapped[FileID] = mapped_column(primary_key=True, index=True, unique=True)
    type: Mapped[str]
    data: Mapped[str]  # VARCHAR ~ Postgres TEXT -- unlimited length (but up to 1gb)

    # objective props:
    kind: Mapped[str] = mapped_column(server_default=schemas.FileKind.IMAGE)
    width: Mapped[float | None]
    height: Mapped[float | None]


class FileToSceneAssociation(DeclarativeFieldsMixin):

    scene_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(Scene.id, ondelete="CASCADE"),
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(File.id, ondelete="CASCADE"),
        index=True,
    )

    __table_args__ = (UniqueConstraint(scene_id, file_id),)


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
