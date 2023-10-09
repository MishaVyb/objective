from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase

from objective.db.meta import meta


class Base(DeclarativeBase):
    """Base for all models."""

    metadata = meta
    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }
