from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated, Any, Type

from pydantic.alias_generators import to_snake
from sqlalchemy import JSON, DateTime, ForeignKey, MetaData, String, engine, func, types
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
from typing_extensions import deprecated

from app.config import AppSettings
from common.schemas.base import BaseSchema

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


STR_255 = Annotated[str, mapped_column(ForceString(255))]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=constraint_naming_conventions)
    type_annotation_map = {
        datetime: _DateTimeForceTimezone(),
        dict: JSON,
        list: JSON,
    }

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

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
        reference_scheme: Type[BaseSchema],
    ) -> list[QueryableAttribute]:
        columns = cls.__table__.columns
        return [
            getattr(cls, fieldname)
            for fieldname in reference_scheme.model_fields
            if fieldname in columns
        ]

    # UNUSED
    @deprecated("")
    def to_dict(self, *, exclude: set[str] = None, include: set[str] = None):
        """Return column names to values mapping. NOTE: relationships are not included, **only columns**."""

        if exclude and include:
            raise ValueError("Mutually exclusive options. ")

        fields = {c.name for c in self.__table__.columns}
        include = include or fields
        exclude = exclude or set()

        if exclude - fields:
            raise ValueError(exclude - fields)
        if include - fields:
            raise ValueError(include - fields)

        return {
            c: getattr(self, c) for c in fields if c in include and c not in exclude
        }


class DeclarativeFieldsMixin(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=datetime.now)

    created_by: Mapped[uuid.UUID] = mapped_column("user_id", ForeignKey("user.id"))
    updated_by: Mapped[uuid.UUID | None]  # TODO foreign key

    is_deleted: Mapped[bool] = mapped_column(default=False)

    @declared_attr
    def user(cls) -> Mapped[User]:
        return relationship("User")
