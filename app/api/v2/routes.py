from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.dependencies.users import AuthRouterDepends
from app.exceptions import DeletedInstanceError
from app.repository.repositories import DatabaseRepositoriesDepends
from app.schemas import schemas
from common.fastapi.monitoring.base import LoggerDepends

########################################################################################
# Projects
########################################################################################


projects = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    dependencies=[AuthRouterDepends],
)


class _ProjectFiltersQuery(schemas.ProjectFilters, as_query=True):
    pass


@projects.get("")
async def get_projects(
    db: DatabaseRepositoriesDepends,
    *,
    filters: Annotated[_ProjectFiltersQuery, Depends()],
) -> schemas.GetProjectsResponse:
    return schemas.GetProjectsResponse(items=await db.projects.get_filter(filters))


@projects.get("/{id}")
async def get_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
) -> schemas.Project:
    return await db.projects.get(id)


@projects.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    db: DatabaseRepositoriesDepends,
    *,
    payload: schemas.ProjectCreate,
) -> schemas.Project:
    return await db.projects.create(payload)


@projects.patch("/{id}", status_code=status.HTTP_200_OK)
async def update_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
    payload: schemas.ProjectUpdate,
) -> schemas.Project:
    return await db.projects.update(id, payload, flush=True)


@projects.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
) -> schemas.Project:
    """Mark as deleted."""
    try:
        return await db.projects.update(id, is_deleted=True)
    except DeletedInstanceError as e:
        return e.instance


########################################################################################
# Scenes
########################################################################################

scenes = APIRouter(prefix="/scenes", tags=["Scenes"], dependencies=[AuthRouterDepends])


class _SceneFiltersQuery(schemas.SceneFilters, as_query=True):
    pass


@scenes.get("")
async def get_scenes(
    db: DatabaseRepositoriesDepends,
    *,
    filters: Annotated[_SceneFiltersQuery, Depends()],
) -> schemas.GetScenesResponse:
    return schemas.GetScenesResponse(items=await db.scenes.get_filter(filters))


@scenes.get("/{scene_id}")
async def get_scene(
    db: DatabaseRepositoriesDepends,
    *,
    scene_id: UUID,
) -> schemas.SceneExtended:
    return await db.scenes.get(scene_id)


@scenes.post("", status_code=status.HTTP_201_CREATED)
async def create_scene(
    db: DatabaseRepositoriesDepends,
    *,
    payload: schemas.SceneCreate,
) -> schemas.SceneExtended:
    return await db.scenes.create(payload, refresh=True)


@scenes.post("/{scene_id}/copy", status_code=status.HTTP_201_CREATED)
async def copy_scene(
    db: DatabaseRepositoriesDepends,
    *,
    scene_id: UUID,
    payload: schemas.SceneCopy,  # overrides
) -> schemas.SceneExtended:
    """Duplicate scene. Supports overrides."""
    original = await db.scenes.get(scene_id)
    payload.project_id = payload.project_id or original.project.id

    p = schemas.SceneCreate.model_build(
        original,
        **payload.model_dump(exclude_unset=True),
        _payload_exclude={"files"},
    )
    scene = await db.scenes.create(p, refresh=True)

    # associate the same files with new scene
    scene.files = original.files
    await db.scenes_simplified.update(
        scene.id,
        schemas.SceneUpdate(files=[file.id for file in original.files]),
    )

    return scene


@scenes.patch("/{scene_id}", status_code=status.HTTP_200_OK)
async def update_scene(
    scene_id: UUID,
    db: DatabaseRepositoriesDepends,
    *,
    payload: schemas.SceneUpdate,
) -> schemas.SceneWithProject:
    return await db.scenes_simplified.update(scene_id, payload, refresh=True)


@scenes.delete("/{scene_id}", status_code=status.HTTP_200_OK)
async def delete_scene(
    db: DatabaseRepositoriesDepends,
    *,
    scene_id: UUID,
) -> schemas.SceneSimplified:
    """Mark as deleted."""
    try:
        return await db.scenes_simplified.update(scene_id, is_deleted=True)
    except DeletedInstanceError as e:
        return e.instance


########################################################################################
# Elements
########################################################################################


class _ElementsFiltersQuery(schemas.ElementsFilters, as_query=True):
    pass


@scenes.get("/{scene_id}/elements", status_code=status.HTTP_200_OK)
async def get_scene_elements(
    scene_id: UUID,
    db: DatabaseRepositoriesDepends,
    *,
    filters: Annotated[_ElementsFiltersQuery, Depends()],
) -> schemas.ReconcileElementsResponse:
    return await db.elements.get(scene_id, filters)


@scenes.post("/{scene_id}/elements", status_code=status.HTTP_200_OK)
async def reconcile_scene_elements(
    scene_id: UUID,
    db: DatabaseRepositoriesDepends,
    *,
    payload: schemas.SyncElementsRequest,
    filters: Annotated[_ElementsFiltersQuery, Depends()],
) -> schemas.ReconcileElementsResponse:
    return await db.elements.reconcile(scene_id, payload, filters)


########################################################################################
# files
########################################################################################


files = APIRouter(prefix="/files", tags=["Files"], dependencies=[AuthRouterDepends])


@files.get("/{id}", status_code=status.HTTP_200_OK)
async def get_file(
    db: DatabaseRepositoriesDepends,
    *,
    id: schemas.FileID,
) -> schemas.FileExtended:
    return await db.files.get_one(id=id)


@files.post("", status_code=status.HTTP_201_CREATED)
async def create_file(
    db: DatabaseRepositoriesDepends,
    logger: LoggerDepends,
    *,
    payload: schemas.FileCreate,
) -> schemas.FileSimplified:

    # the same file might be created many times
    # - when user upload the same image again
    # - when scene is duplicated (copied), its ExcalidrawImageElements has the same file_id
    #  and its render files (i.e. thumbnail, etc) has the same file_id
    # - when user add thumbnail/render file directly to the scene canvas
    # (in that case we do not change file kind)
    if file := await db.files.get_one_or_none(id=payload.id):
        logger.warning("Duplicate file id: %s. File already exist. ", file.id)
        return file

    return await db.files.create(payload)
