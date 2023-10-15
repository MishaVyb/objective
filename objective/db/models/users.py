from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column

from objective.db.base import Base

if TYPE_CHECKING:
    from objective.db.models.scenes import FileModel, ProjectModel, SceneModel


class UserModel(SQLAlchemyBaseUserTableUUID, Base):
    """Represents a user entity."""

    # base:
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    # extra info:
    username: Mapped[str | None]
    role: Mapped[str | None]

    # relationships
    if TYPE_CHECKING:
        projects: Mapped[list[ProjectModel]]
        scenes: Mapped[list[SceneModel]]
        files: Mapped[list[FileModel]]
    else:
        pass  # postponed definition
