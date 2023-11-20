from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)


# NOTE
# Scene is allowed to be updated PARTIALLY, so there are all fields are optional
class SceneBaseSchema(BaseSchema):
    # TODO validate: project_id belongs to user
    project_id: UUID | None = None  # update that means move to another project
    name: str | None = None


class SceneExtendedSchema(SceneBaseSchema):
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: Any | None = None
    app_state: Any | None = Field(default=None, alias="appState")


class SceneCreateSchema(SceneExtendedSchema, BaseCreateSchema):
    project_id: UUID  # required


class SceneUpdateSchema(SceneExtendedSchema, BaseUpdateSchema):
    pass


class SceneSimplifiedReadSchema(SceneBaseSchema, BaseReadSchema):
    pass


class SceneExtendedReadSchema(SceneExtendedSchema, BaseReadSchema):
    ...

    # files: list # TODO
