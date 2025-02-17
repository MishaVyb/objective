from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated

import fastapi_users
from pydantic import Field

from common.schemas.base import ITEM_PG_ID, BaseSchema

from .base import (
    CreateSchemaMixin,
    CreateWithIDSchemaMixin,
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
# scenes
########################################################################################


class SceneSimplified(BaseSchema, DeclarativeFieldsMixin):
    name: str
    app_state: AppState

    # relations:
    files: list[FileSimplified] = Field(
        description=(
            f"Files that manually associated with that scene (i.e. `thumbnail`, `export`). "
            "User's image files have not direct association with the scene, "
            "but it cant be found through scene elements by `element.file_id`. "
        ),
    )
    """Scene's `renders` (not user's `images`). """

    # Excalidraw extra # UNUSED
    type: str | None = None
    version: int | None = None
    source: str | None = None


class SceneWithProject(SceneSimplified):
    project: ProjectSimplified


class SceneExtended(SceneWithProject):
    """Scene with project and elements."""

    elements: list[Element]


class SceneCreate(
    SceneExtended,
    CreateSchemaMixin,
    exclude={"project"},
    optional={"elements", "app_state"},
):
    files: list[FileCreate] = []
    """User's `images` (not `renders`). It's required for creating scenes from '.objective' file. """
    project_id: ITEM_PG_ID


class SceneUpdate(
    SceneExtended,
    UpdateSchemaMixin,
    optional=SceneCreate.model_fields,
    exclude={"project", "elements"},
):
    files: list[FileID] | None = None  # update files (thumbnails/exports)
    project_id: ITEM_PG_ID | None = None  # move scene to another project


class SceneCopy(SceneUpdate, exclude={"files"}):
    pass


class GetScenesResponse(ItemsResponseBase[SceneExtended]):
    pass


########################################################################################
# AppState/Elements
########################################################################################


ElementID = Annotated[str, ...]


class AppState(BaseSchema, extra="allow"):
    """
    Partial Excalidraw app state.

    :see clearAppStateForDatabase: `objective-f` implements `clearAppStateForDatabase`.
    :note name: `AppState.name` is deprecated and `Scene.name` should be used instead.
    """


class Element(BaseSchema, extra="allow"):
    id: ElementID
    is_deleted: bool

    # Meta for synchronization:

    version: int
    """
    Integer that is sequentially incremented on each change. Used to reconcile
    elements during collaboration or when saving to server.
    """
    version_nonce: int
    """
    Random integer that is regenerated on each change.
    Used for deterministic reconciliation of updates during collaboration,
    in case the versions (see above) are identical.
    """
    updated: float
    """Epoch (ms) timestamp of last element update. """

    # Excalidraw Image Element props:

    class FileStatus(StrEnum):
        pending = "pending"
        saved = "saved"
        error = "error"

    file_id: str | None = None
    status: FileStatus | None = None


class GetElementsResponse(ItemsResponseBase[Element]):
    next_sync_token: float


class SyncElementsRequest(BaseSchema):
    items: list[Element]
    """Elements to append or/and reconcile with current Scene elements. """


class ReconcileElementsResponse(GetElementsResponse):
    pass


########################################################################################
# files
########################################################################################

FileID = Annotated[str, ...]
"""File id length equals 40 to align with the HEX length of SHA-1 (which is 160 bit). """


class FileKind(StrEnum):
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
    RENDER = "render"


class FileSimplified(BaseSchema, DeclarativeFieldsMixin):
    id: FileID
    type: str = Field(alias="mimeType")

    # objective props:
    kind: FileKind = FileKind.IMAGE
    width: float | None = None
    height: float | None = None


class FileExtended(FileSimplified):
    data: str = Field(alias="dataURL")


class FileCreate(FileExtended, CreateWithIDSchemaMixin):
    id: FileID


########################################################################################
# filters
########################################################################################


class FiltersBase(BaseSchema):
    class CreatedBy(StrEnum):
        current_user = "current_user"
        any = "*"

    created_by_id: uuid.UUID | CreatedBy = CreatedBy.current_user
    is_deleted: bool | None = None


class ProjectFilters(FiltersBase):
    pass


class SceneFilters(FiltersBase):
    project_id: uuid.UUID | None = None


class ElementsFilters(BaseSchema):
    sync_token: float = 0.0


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
    app_state: dict = {}
    files: dict[FileID, FileJsonPersistence]

    @property
    def name(self) -> str:
        return self.app_state.get("name") or "Untitled Scene"
