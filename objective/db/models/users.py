from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from objective.db.base import Base

if TYPE_CHECKING:
    from objective.db.models.scenes import ProjectModel, SceneModel


class UserModel(SQLAlchemyBaseUserTableUUID, Base):
    """Represents a user entity."""

    # base:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(),
    )

    # extra info:
    username: Mapped[str | None]
    role: Mapped[str | None]

    # relationships (postponed definition)
    if TYPE_CHECKING:
        projects: Mapped[ProjectModel]
        scenes: Mapped[SceneModel]
