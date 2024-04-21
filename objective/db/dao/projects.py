from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import selectinload

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import FileModel, ProjectModel, SceneModel
from objective.schemas.projects import (
    ProjectCreateSchema,
    ProjectUpdateSchema,
    SceneSimplifiedReadSchema,
)
from objective.schemas.scenes import FileBaseSchema, SceneJSONFileSchema


@dataclass
class ProjectFilters(FiltersBase):
    pass


class ProjectRepository(
    RepositoryBase[ProjectModel, ProjectCreateSchema, ProjectUpdateSchema],
):
    model = ProjectModel
    options_one = [
        #
        # scenes
        selectinload(ProjectModel.scenes).load_only(
            *SceneModel.columns_depending_on(SceneSimplifiedReadSchema), raiseload=True
        ),
        #
        # scene files
        selectinload(ProjectModel.scenes)
        .selectinload(SceneModel.files)
        .load_only(*FileModel.columns_depending_on(FileBaseSchema), raiseload=True),
    ]
    options_many = options_one

    DEFAULT_PROJECT_NAME = "Default Project"
    DEFAULT_SCENE_NAME = "Untitled Scene"

    async def create(self, schema: ProjectCreateSchema, **extra_values):
        return await super().create(schema, **extra_values)

    async def create_default(self, request: Request | None = None):
        initial: list[SceneJSONFileSchema] = request.app.state.initial_scenes
        scenes = [
            SceneModel(
                name=scene.app_state.get("name") or self.DEFAULT_SCENE_NAME,
                user_id=self.user.id,
                files=[
                    FileModel(
                        user_id=self.user.id,
                        **f.model_dump(),
                    )
                    for f in scene.files.values()
                ],
                **scene.model_dump(exclude={"files"}),
            )
            for scene in initial
        ]

        return await self.create(
            ProjectCreateSchema(name=self.DEFAULT_PROJECT_NAME),
            scenes=scenes,
        )
