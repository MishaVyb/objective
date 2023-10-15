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
        return [getattr(cls, fieldname) for fieldname in reference_scheme.model_fields]
