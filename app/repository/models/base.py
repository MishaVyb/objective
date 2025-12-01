from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Type

from pydantic.alias_generators import to_snake
from sqlalchemy import JSON, DateTime, ForeignKey, MetaData, String, engine, types
from sqlalchemy.dialects.sqlite.base import SQLiteDialect
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    QueryableAttribute,
    declared_attr,
    mapped_column,
    relationship,
)
from sqlalchemy.orm.exc import DetachedInstanceError

from app.config import AppSettings
from common.schemas.base import SchemaBase

if TYPE_CHECKING:
    from app.repository.models.users import User


constraint_naming_conventions = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# NOTE workaround fro SQLAlchemy and SQLite issue
# https://github.com/sqlalchemy/sqlalchemy/issues/1985
class _DateTimeForceTimezone(types.TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(
        self,
        value: datetime | None,
        dialect: engine.interfaces.Dialect,
    ):
        if value and isinstance(dialect, SQLiteDialect):
            return value.replace(tzinfo=timezone.utc)
        return value


# NOTE: enforce storing python value as simple string
class ForceString(types.TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: engine.interfaces.Dialect):
        if value:
            return str(value)
        return value


class DatabaseStringEnum(types.TypeDecorator):
    impl = String()
    cache_ok = True

    def __init__(self, enum_class: Type[StrEnum], *args: Any, **kwargs: Any) -> None:
        self._enum_class = enum_class
        super().__init__(*args, **kwargs)

    def process_bind_param(
        self,
        value: Any | None,
        dialect: engine.interfaces.Dialect,
    ) -> None | str:
        if value is None:
            return value
        return str(value)

    def process_result_value(
        self,
        value: Any | None,
        dialect: engine.interfaces.Dialect,
    ) -> None | StrEnum:
        if value is None:
            return value
        return self._enum_class(value)


STR_255 = Annotated[str, mapped_column(ForceString(255))]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=constraint_naming_conventions)
    type_annotation_map = {
        datetime: _DateTimeForceTimezone(),
        dict: JSON,
        list: JSON,
    }

    id: uuid.UUID

    @classmethod
    def setup(cls, settings: AppSettings):
        """Postponed database model declarations. When settings are required."""

    def __repr__(self):
        try:
            return f"<{self.__class__.__name__}({self.id=})>"
        except DetachedInstanceError:
            return f"<{self.__class__.__name__}(detached)>"

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return to_snake(cls.__name__)

    @classmethod
    def columns_depending_on(
        cls,
        reference_scheme: Type[SchemaBase],
    ) -> list[QueryableAttribute]:
        columns = cls.__table__.columns
        return [
            getattr(cls, fieldname)
            for fieldname in reference_scheme.model_fields
            if fieldname in columns
        ]


class DeclarativeFieldsMixin(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=lambda: uuid.uuid4(),
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        index=True,  # for ORDER_BY better performance
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ex 'user_id' column
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id"),
        index=True,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id"),
        default=None,
        index=True,
    )

    @declared_attr
    @classmethod
    def created_by(cls) -> Mapped["User"]:
        return relationship(foreign_keys=[cls.created_by_id])

    is_deleted: Mapped[bool] = mapped_column(default=False)
