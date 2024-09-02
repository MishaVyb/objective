import uuid

from pydantic import AwareDatetime, Field

from common.schemas.base import ModelConstructor


class DeclarativeFieldsMixin(ModelConstructor):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)

    created_by_id: uuid.UUID | None = None
    updated_by_id: uuid.UUID | None = None
    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None

    is_deleted: bool = False


class CreateSchemaMixin(
    DeclarativeFieldsMixin,
    exclude=DeclarativeFieldsMixin.model_fields,
):
    pass


class UpdateSchemaMixin(
    CreateSchemaMixin,
    include={"is_deleted"},
):
    pass
