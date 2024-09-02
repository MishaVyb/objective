from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

if TYPE_CHECKING:
    from .scenes import File, Project, Scene


class User(SQLAlchemyBaseUserTableUUID, Base):

    # declarative fields:
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    # custom extra fields:
    username: Mapped[str | None]
    role: Mapped[str | None]

    # relationships:

    if TYPE_CHECKING:
        projects: Mapped[list[Project]]
        scenes: Mapped[list[Scene]]
        files: Mapped[list[File]]
    else:
        pass  # postponed definition
