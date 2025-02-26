import uuid
import warnings
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import AwareDatetime, Field

from common.schemas.base import SchemaBase

# enable pydantic warning as error to not miss type mismatch
warnings.filterwarnings("error", r"Pydantic serializer warnings")


class DeclarativeSchemaBase(SchemaBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)

    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID | None
    created_at: AwareDatetime
    updated_at: AwareDatetime | None

    is_deleted: bool = False

    def __repr_args__(self):
        yield ("id", self.id)


class CreateSchemaBase(
    DeclarativeSchemaBase,
    exclude=DeclarativeSchemaBase.model_fields,
):
    def __repr_args__(self):
        yield from SchemaBase.__repr_args__(self)  # using model fields set


class CreateWithIDSchemaBase(
    DeclarativeSchemaBase,
    exclude=set(DeclarativeSchemaBase.model_fields) - {"id"},
):
    pass


class UpdateSchemaBase(
    DeclarativeSchemaBase,
    # NOTE
    # it allows DELETE instances by UPDATE
    exclude=set(DeclarativeSchemaBase.model_fields) - {"is_deleted"},
    optional={"is_deleted"},
):
    @property
    def is_update_recover(self) -> bool:
        return "is_deleted" in self.model_fields_set and self.is_deleted == False

    def __repr_args__(self):
        yield from SchemaBase.__repr_args__(self)  # using model fields set


_T = TypeVar("_T", bound=SchemaBase)


class ItemsResponseBase(SchemaBase, Generic[_T]):
    items: list[_T]


class Access(StrEnum):
    PRIVATE = "private"
    PROTECTED = "protected"  # can be viewed by anyone with a link (but not edit)
    PUBLIC = "public"  # can be viewed and edited by anyone with a link


class EntityMixin(DeclarativeSchemaBase):
    access: Access
