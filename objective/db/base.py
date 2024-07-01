from typing import Type

from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, QueryableAttribute

from objective.db.meta import meta
from objective.schemas.base import BaseSchema


class Base(DeclarativeBase):
    """Base for all models."""

    metadata = meta
    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }

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
