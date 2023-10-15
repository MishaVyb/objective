from dataclasses import dataclass

from sqlalchemy.orm import selectinload

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import ProjectModel, SceneModel
from objective.schemas.projects import (
    ProjectCreateSchema,
    ProjectUpdateSchema,
    SceneReadSimplifiedSchema,
)


@dataclass
class ProjectFilters(FiltersBase):
    pass


class ProjectRepository(
    RepositoryBase[ProjectModel, ProjectCreateSchema, ProjectUpdateSchema],
):
    model = ProjectModel
    options_many = [
        selectinload(ProjectModel.scenes).load_only(
            *SceneModel.columns_depending_on(SceneReadSimplifiedSchema), raiseload=True
        ),
    ]

    DEFAULT_PROJECT_NAME = "Default Project"
    DEFAULT_SCENE_NAME = "Untitled Scene"

    async def create(self, schema: ProjectCreateSchema, **extra_values):
        return await super().create(
            schema,
            **extra_values,
            scenes=[
                # default Scene for every new Project:
                SceneModel(name=self.DEFAULT_SCENE_NAME, user_id=self.user.id),
            ]
        )

    async def create_default(self):
        return await self.create(ProjectCreateSchema(name=self.DEFAULT_PROJECT_NAME))
