from typing import Literal

from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from objective.schemas.scenes import SceneSimplifiedReadSchema


class ProjectBaseSchema(BaseSchema):
    name: str


class ProjectCreateSchema(ProjectBaseSchema, BaseCreateSchema):
    pass


class ProjectUpdateSchema(ProjectBaseSchema, BaseUpdateSchema):
    name: str | None = None
    is_deleted: Literal[False] | None = None


class ProjectReadSchema(ProjectBaseSchema, BaseReadSchema):
    scenes: list[SceneSimplifiedReadSchema] | None  # TODO default ?


class SceneBaseSchema(BaseSchema):
    name: str
