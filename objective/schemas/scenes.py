from __future__ import annotations

from uuid import UUID

from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)


class SceneBaseSchema(BaseSchema):
    project_id: UUID
    name: str


class SceneCreateSchema(SceneBaseSchema, BaseCreateSchema):
    pass


class SceneUpdateSchema(SceneBaseSchema, BaseUpdateSchema):
    pass


class SceneReadSimplifiedSchema(SceneBaseSchema, BaseReadSchema):
    pass


class SceneReadSchema(SceneBaseSchema, BaseReadSchema):

    # scene data:
    type: str | None
    version: int | None
    source: str | None
    elements: list
    app_state: dict

    # files: list # TODO
