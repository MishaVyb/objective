import uuid
from typing import Generic, TypeVar

from pydantic import AwareDatetime, Field

from common.schemas.base import BaseSchema, ModelConstructor


class DeclarativeFieldsMixin(ModelConstructor):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)

    created_by_id: uuid.UUID | None = Field(default=None, alias="user_id")
    updated_by_id: uuid.UUID | None = None
    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None

    is_deleted: bool = False


class CreateSchemaMixin(
    DeclarativeFieldsMixin,
    # NOTE
    # it allows CREATE instances with ID (for Files / Elements)
    exclude=set(DeclarativeFieldsMixin.model_fields) - {"id"},
):
    pass


class UpdateSchemaMixin(
    DeclarativeFieldsMixin,
    # NOTE
    # it allows DELETE instances by UPDATE
    exclude=set(DeclarativeFieldsMixin.model_fields) - {"is_deleted"},
    optional={"is_deleted"},
):
    @property
    def is_update_recover(self) -> bool:
        return "is_deleted" in self.model_fields_set and self.is_deleted == False


_T = TypeVar("_T", bound=BaseSchema)


class ItemsResponseBase(BaseSchema, Generic[_T]):
    items: list[_T]
