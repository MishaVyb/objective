import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from objective.db.meta import meta


class Base(DeclarativeBase):
    """Base for all models."""

    metadata = meta
    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }


class BaseModelFieldsMixin:

    if TYPE_CHECKING:

        def __init__(self, *args, **kwargs) -> None:
            pass

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        onupdate=func.current_timestamp(),
    )
    """Resolve simultaneously updates. """
    updated_by: Mapped[uuid.UUID | None]
    """Supports collab mode. """
    is_deleted: Mapped[bool] = mapped_column(default=False)
    """Supports deleting for client, but archive on backend. """

    # relations:
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
