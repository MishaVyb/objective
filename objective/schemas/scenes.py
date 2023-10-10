from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)


class ProjectBaseSchema(BaseSchema):
    name: str


class ProjectCreateSchema(ProjectBaseSchema, BaseCreateSchema):
    pass


class ProjectUpdateSchema(ProjectBaseSchema, BaseUpdateSchema):
    pass


class ProjectReadSchema(ProjectBaseSchema, BaseReadSchema):
    ...
    # scenes: list[UUID] # TODO as list[SceneReadSimplifiedSchema]
