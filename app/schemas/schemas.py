from __future__ import annotations

import uuid
from typing import Literal, TypeAlias

import fastapi_users
from pydantic import Field

from common.schemas.base import BaseSchema

from .base import CreateSchemaMixin, DeclarativeFieldsMixin, UpdateSchemaMixin


class FiltersBase(BaseSchema):
    created_by_id: uuid.UUID | Literal["current_user"] | Literal[""] | None = Field(
        default="current_user",
        alias="user_id",
    )
    is_deleted: bool | None = None


########################################################################################
# users
########################################################################################


class _UserFieldsMixin(BaseSchema):
    username: str | None = None
    role: str | None = None


class User(fastapi_users.schemas.BaseUser[uuid.UUID], _UserFieldsMixin):
    pass


class UserCreate(fastapi_users.schemas.BaseUserCreate, _UserFieldsMixin):
    pass


class UserUpdate(fastapi_users.schemas.BaseUserUpdate, _UserFieldsMixin):
    pass


########################################################################################
# projects
########################################################################################


class Project(BaseSchema, DeclarativeFieldsMixin):
    name: str

    # relations
    scenes: list[SceneSimplified]


class ProjectCreate(
    Project,
    CreateSchemaMixin,
    exclude={"scenes"},
):
    pass


class ProjectUpdate(
    ProjectCreate,
    UpdateSchemaMixin,
    optional=ProjectCreate.model_fields,
):
    pass


class ProjectFilters(FiltersBase):
    pass


########################################################################################
# files
########################################################################################

FileId: TypeAlias = str


class FileSimplified(BaseSchema, DeclarativeFieldsMixin):
    # id - not needed, using `file_id` for get / post requests
    file_id: FileId = Field(
        description="Excalidraw file id",
        validation_alias="file_id",  # from database
        serialization_alias="id",  # to Excalidraw
    )
    type: str = Field(alias="mimeType")


class FileExtended(FileSimplified):
    data: str = Field(alias="dataURL")


class FileCreate(FileExtended, CreateSchemaMixin):
    file_id: FileId = Field(
        description="Excalidraw file id",
        validation_alias="id",  # from Excalidraw
        serialization_alias="file_id",  # to Database
    )


########################################################################################
# scenes
########################################################################################


class SceneSimplified(BaseSchema, DeclarativeFieldsMixin):
    name: str
    project_id: uuid.UUID

    # relations
    files: list[FileSimplified] = []


class SceneExtended(SceneSimplified):
    type: str
    version: int
    source: str
    elements: list
    app_state: dict = Field(alias="appState")


class SceneCreate(
    SceneExtended,
    CreateSchemaMixin,
):
    files: list[FileCreate] = []  # ???


class SceneUpdate(
    UpdateSchemaMixin,
    SceneExtended,
    #
    # Do not need files here as we add new files to scene by POST .../scene/files/
    exclude={"files"},
):
    pass


class SceneFilters(FiltersBase):
    project_id: uuid.UUID | None = None


########################################################################################
# other
########################################################################################


class SceneJsonFilePersistence(BaseSchema):  # from .objective JSON files
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: list = []
    app_state: dict = Field(default={}, alias="appState")
    files: dict[FileId, FileCreate]
