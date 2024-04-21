from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from objective.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseSchema,
    BaseUpdateSchema,
)


class FileBaseSchema(BaseSchema):
    # id - not needed, using `file_id` for get / post requests
    file_id: str = Field(
        description="Excalidraw file id",
        validation_alias="file_id",  # from database
        serialization_alias="id",  # to Excalidraw
    )
    type: str = Field(alias="mimeType")


class FileExtendedSchema(FileBaseSchema):
    data: str = Field(alias="dataURL")


class FileCreateSchema(FileExtendedSchema, BaseCreateSchema):
    file_id: str = Field(
        description="Excalidraw file id",
        validation_alias="id",  # from Excalidraw
        serialization_alias="file_id",  # to Database
    )


# NOTE
# Scene is allowed to be updated PARTIALLY, so there are all fields are optional
class SceneBaseSchema(BaseSchema):
    # TODO validate: project_id belongs to user
    project_id: UUID | None = None  # update that means move to another project
    name: str | None = None


class SceneExtendedSchema(SceneBaseSchema):
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: Any | None = None
    app_state: Any | None = Field(default=None, alias="appState")


class SceneCreateSchema(SceneExtendedSchema, BaseCreateSchema):
    project_id: UUID  # required

    # TODO
    # files: list[FileBaseSchema] = []


FileId = str


class SceneJSONFileSchema(BaseSchema):
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: Any | None = None
    app_state: Any | None = Field(default=None, alias="appState")
    files: dict[FileId, FileCreateSchema]


class SceneUpdateSchema(SceneExtendedSchema, BaseUpdateSchema):
    pass

    # Do not need files here as we add new files to scene by POST .../scene/files/
    # files: list[FileBaseSchema] = []


class SceneSimplifiedReadSchema(SceneBaseSchema, BaseReadSchema):
    files: list[FileBaseSchema] = []


class SceneExtendedReadSchema(SceneExtendedSchema, BaseReadSchema):
    files: list[FileBaseSchema] = []


# NOTE new naming convention here, TODO the same for others
class GetSceneResponse(SceneExtendedSchema, BaseReadSchema):
    files: list[FileBaseSchema] = []


class UpdateSceneResponse(SceneExtendedSchema, BaseReadSchema):
    files: list[FileBaseSchema] = []
