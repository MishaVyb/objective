from dataclasses import dataclass

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import SceneModel
from objective.schemas.scenes import SceneCreateSchema, SceneUpdateSchema


@dataclass
class SceneFilters(FiltersBase):
    pass


class SceneRepository(
    RepositoryBase[SceneModel, SceneCreateSchema, SceneUpdateSchema],
):
    model = SceneModel
