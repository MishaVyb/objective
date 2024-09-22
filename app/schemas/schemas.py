from __future__ import annotations

import uuid
from typing import Literal, TypeAlias

import fastapi_users
from pydantic import Field

from common.schemas.base import ITEM_PG_ID, BaseSchema

from .base import (
    CreateSchemaMixin,
    DeclarativeFieldsMixin,
    ItemsResponseBase,
    UpdateSchemaMixin,
)

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


class ProjectSimplified(Project, DeclarativeFieldsMixin, exclude={"scenes"}):
    pass


class ProjectCreate(Project, CreateSchemaMixin, exclude={"scenes"}):
    pass


class ProjectUpdate(
    Project,
    UpdateSchemaMixin,
    exclude={"scenes"},
    optional=ProjectCreate.model_fields,
):
    pass


class GetProjectsResponse(ItemsResponseBase[Project]):
    pass


########################################################################################
# files
########################################################################################

FileID: TypeAlias = str


class FileSimplified(BaseSchema, DeclarativeFieldsMixin):
    # NOTE:
    # Postgres UUID - not required, using `file_id` for get / post requests
    file_id: FileID = Field(
        description="Excalidraw file id",
        # NOTE
        # cannot use simple alias='id', as it would be populated from PG id value in first
        # place, not from 'file_id' column
        validation_alias="file_id",  # from database
        serialization_alias="id",  # to Excalidraw
    )
    type: str | None = Field(None, alias="mimeType")


class FileExtended(FileSimplified):
    data: str = Field(alias="dataURL")


class FileCreate(FileExtended, CreateSchemaMixin):
    file_id: FileID = Field(
        description="Excalidraw file id",
        validation_alias="id",  # from Excalidraw
        serialization_alias="file_id",  # to Database
    )


########################################################################################
# scenes
########################################################################################


class SceneSimplified(BaseSchema, DeclarativeFieldsMixin):
    name: str

    # # relations
    # project_id: uuid.UUID  # DEPRECATED self.project should be used


class SceneExtended(SceneSimplified):
    elements: list
    app_state: dict = Field(alias="appState")

    # relations:
    project: ProjectSimplified

    # other (unused)
    type: str | None = None
    version: int | None = None
    source: str | None = None


class SceneCreate(SceneExtended, CreateSchemaMixin, exclude={"project"}):
    elements: list = []
    app_state: dict = Field(default={}, alias="appState")

    # relations:
    files: list[FileCreate] = []
    project_id: ITEM_PG_ID


class SceneUpdate(
    SceneExtended,
    UpdateSchemaMixin,
    optional=SceneExtended.model_fields,
):
    # relations
    project: ITEM_PG_ID = Field(alias="project_id")


class GetScenesResponse(ItemsResponseBase[SceneExtended]):
    pass


########################################################################################
# Elements
########################################################################################


class Element(BaseSchema, extra="allow"):
    ...


class GetElementsResponse(ItemsResponseBase[Element]):
    next_sync_token: str | None = None


########################################################################################
# Filters
########################################################################################


class FiltersBase(BaseSchema):
    created_by_id: uuid.UUID | Literal["current_user"] | Literal[""] = Field(
        default="current_user",
        alias="user_id",
    )
    is_deleted: bool | None = None


class ProjectFilters(FiltersBase):
    pass


class SceneFilters(FiltersBase):
    project_id: uuid.UUID | None = None


########################################################################################
# other
########################################################################################


# from .objective JSON files
class FileJsonPersistence(FileCreate, extra="ignore"):
    pass


class SceneJsonFilePersistence(BaseSchema, extra="ignore"):
    type: str | None = None
    version: int | None = None
    source: str | None = None
    elements: list = []
    app_state: dict = Field(default={}, alias="appState")
    files: dict[FileID, FileJsonPersistence]

    @property
    def name(self) -> str:
        return self.app_state.get("name") or "Untitled Scene"
