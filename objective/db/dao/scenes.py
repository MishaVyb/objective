from dataclasses import dataclass

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import ProjectModel
from objective.schemas.scenes import ProjectCreateSchema, ProjectUpdateSchema


@dataclass
class ProjectFilters(FiltersBase):
    pass


class ProjectRepository(
    RepositoryBase[ProjectModel, ProjectCreateSchema, ProjectUpdateSchema],
):
    model = ProjectModel

    DEFAULT_PROJECT_NAME = "Default Project"

    async def create_default(self):
        return await self.create(ProjectCreateSchema(name=self.DEFAULT_PROJECT_NAME))
