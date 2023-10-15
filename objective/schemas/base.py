from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class BaseCreateSchema(BaseModel):
    pass


class BaseUpdateSchema(BaseModel):
    pass


class BaseReadSchema(BaseSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime | None
    updated_by: UUID | None
    is_deleted: bool

    # relations:
    user_id: UUID
