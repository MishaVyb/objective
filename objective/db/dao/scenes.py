from dataclasses import dataclass

from sqlalchemy.orm import selectinload

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import FileModel, SceneModel
from objective.schemas.scenes import (
    FileCreateSchema,
    SceneCreateSchema,
    SceneUpdateSchema,
)


@dataclass
class SceneFilters(FiltersBase):
    pass


class SceneRepository(
    RepositoryBase[SceneModel, SceneCreateSchema, SceneUpdateSchema],
):
    model = SceneModel
    options_one = [
        selectinload(SceneModel.files).load_only(
            FileModel.id,
            FileModel.file_id,
            FileModel.type,
            raiseload=True,
        ),
    ]


class FileRepository(
    RepositoryBase[FileModel, FileCreateSchema, None],
):
    model = FileModel
