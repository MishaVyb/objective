from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from objective.schemas.scenes import SceneReadSimplifiedSchema


class ProjectBaseSchema(BaseSchema):
    name: str


class ProjectCreateSchema(ProjectBaseSchema, BaseCreateSchema):
    pass


class ProjectUpdateSchema(ProjectBaseSchema, BaseUpdateSchema):
    pass


class ProjectReadSchema(ProjectBaseSchema, BaseReadSchema):
    scenes: list[SceneReadSimplifiedSchema] | None  # TODO default []


class SceneBaseSchema(BaseSchema):
    name: str
