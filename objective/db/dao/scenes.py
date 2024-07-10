from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import selectinload

from objective.db.dao.base import FiltersBase, RepositoryBase
from objective.db.models.scenes import FileModel, SceneModel
from objective.schemas.scenes import (
    FileBaseSchema,
    FileCreateSchema,
    SceneCreateSchema,
    SceneUpdateSchema,
)


@dataclass
class SceneFilters(FiltersBase):
    project_id: UUID | None = None


class SceneRepository(
    RepositoryBase[SceneModel, SceneCreateSchema, SceneUpdateSchema],
):
    model = SceneModel
    options_load_files = [
        selectinload(SceneModel.files).load_only(
            *FileModel.columns_depending_on(FileBaseSchema), raiseload=True
        ),
    ]
    options_one = options_load_files + [
        selectinload(SceneModel.project),
    ]
    options_many = options_load_files + [
        selectinload(SceneModel.project),
    ]


class FileRepository(
    RepositoryBase[FileModel, FileCreateSchema, None],
):
    model = FileModel
