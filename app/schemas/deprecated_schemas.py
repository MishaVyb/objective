from __future__ import annotations

import uuid
from typing import Literal, TypeAlias

import fastapi_users
from pydantic import ConfigDict, Field
from typing_extensions import deprecated

from common.schemas.base import ITEM_PG_ID, BaseSchema

from .base import CreateSchemaMixin, DeclarativeFieldsMixin, UpdateSchemaMixin


@deprecated("")
class FiltersBase(BaseSchema):
    created_by_id: uuid.UUID | Literal["current_user"] | Literal[""] = Field(
        default="current_user",
        alias="user_id",
    )
    is_deleted: bool | None = None


########################################################################################
# users
########################################################################################


@deprecated("")
class _UserFieldsMixin(BaseSchema):
    username: str | None = None
    role: str | None = None


@deprecated("")
class User(fastapi_users.schemas.BaseUser[uuid.UUID], _UserFieldsMixin):
    pass


@deprecated("")
class UserCreate(fastapi_users.schemas.BaseUserCreate, _UserFieldsMixin):
    pass


@deprecated("")
class UserUpdate(fastapi_users.schemas.BaseUserUpdate, _UserFieldsMixin):
    pass


########################################################################################
# projects
########################################################################################


@deprecated("")
class Project(BaseSchema, DeclarativeFieldsMixin):
    name: str

    # relations
    scenes: list[SceneSimplified]


@deprecated("")
class ProjectSimplified(Project, DeclarativeFieldsMixin, exclude={"scenes"}):
    pass


@deprecated("")
class ProjectCreate(Project, CreateSchemaMixin, exclude={"scenes"}):
    pass


@deprecated("")
class ProjectUpdate(
    Project,
    UpdateSchemaMixin,
    exclude={"scenes"},
    optional=ProjectCreate.model_fields,
):
    pass


@deprecated("")
class ProjectFilters(FiltersBase):
    pass


########################################################################################
# files
########################################################################################

FileId: TypeAlias = str


@deprecated("")
class FileSimplified(BaseSchema, DeclarativeFieldsMixin):
    # NOTE:
    # Postgres UUID - not required, using `file_id` for get / post requests
    file_id: FileId = Field(
        description="Excalidraw file id",
        # alias='id',
        validation_alias="file_id",  # from database
        serialization_alias="id",  # to Excalidraw
    )
    type: str | None = Field(None, alias="mimeType")


@deprecated("")
class FileExtended(FileSimplified):
    data: str = Field(alias="dataURL")


@deprecated("")
class FileCreate(FileExtended, CreateSchemaMixin):
    file_id: FileId = Field(
        # alias='id',
        description="Excalidraw file id",
        validation_alias="id",  # from Excalidraw
        serialization_alias="file_id",  # to Database
    )

    # BACKWARDS CAPABILITY
    model_config = ConfigDict(extra="ignore")


########################################################################################
# scenes
########################################################################################


@deprecated("")
class SceneSimplified(BaseSchema, DeclarativeFieldsMixin):
    name: str

    # relations
    files: list[FileSimplified] = []
    project_id: uuid.UUID  # DEPRECATED self.project should be used


@deprecated("")
class SceneExtended(SceneSimplified):
    elements: list
    app_state: dict = Field(alias="appState")

    # relations:
    project: ProjectSimplified

    # other (unused)
    type: str | None = None
    version: int | None = None
    source: str | None = None


@deprecated("")
class SceneCreate(SceneExtended, CreateSchemaMixin, exclude={"project"}):
    elements: list = []
    app_state: dict = Field(default={}, alias="appState")

    # relations:
    files: list[FileCreate] = []
    project: ITEM_PG_ID = Field(alias="project_id")


@deprecated("")
class SceneUpdate(
    SceneExtended,
    UpdateSchemaMixin,
    #
    # Do not need files here as we add new files to scene by POST .../scene/files/
    exclude={"files"},
    optional=SceneExtended.model_fields,
):
    # relations
    project: ITEM_PG_ID = Field(alias="project_id")


@deprecated("")
class SceneFilters(FiltersBase):
    project_id: uuid.UUID | None = None


########################################################################################
# other
########################################################################################


@deprecated("")
class SceneJsonFilePersistence(BaseSchema):  # from .objective JSON files
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: list = []
    app_state: dict = Field(default={}, alias="appState")
    files: dict[FileId, FileCreate]
