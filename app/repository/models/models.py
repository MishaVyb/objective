from __future__ import annotations

import time
import uuid

from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.schemas.schemas import ElementID, FileID

from .base import Base, DeclarativeFieldsMixin
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


class Element(Base):
    # Excalidraw
    id: Mapped[ElementID] = mapped_column()  # uniq per scene_id

    # Meta for synchronization (resolve merging conflicts)
    version: Mapped[int]
    version_nonce: Mapped[int]
    updated: Mapped[float]

    # ExcalidrawImageElement props
    file_id: Mapped[str | None]
    status: Mapped[str | None]

    _json: Mapped[dict]
    # _updated: Mapped[datetime] = mapped_column(
    #     default=lambda: datetime.now(timezone.utc),
    #     onupdate=lambda: datetime.now(timezone.utc),
    # )
    _updated: Mapped[int] = mapped_column(
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
