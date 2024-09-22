from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.dependencies.users import AuthRouterDepends
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
    return await db.projects.update(id, payload)


@projects.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
) -> schemas.Project:
    """Mark as deleted."""
    return await db.projects.update(id, is_deleted=True)


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
    payload: schemas.SceneUpdate,  # overrides
    logger: LoggerDepends,
) -> schemas.SceneExtended:
    """Duplicate scene. Supports overrides."""
    original = await db.scenes.get(scene_id)

    # # handle files:
    # if original.created_by_id != db.users.current_user.id:
    #     logger.info("Coping external scene. Handle file. ")

    #     tasks: list[Task[schemas.FileExtended]] = []
    #     async with TaskGroup() as tg:
    #         for file in original.files:
    #             coro = db.files.get_one(
    #                 file_id=file.file_id, created_by_id=file.created_by_id
    #             )
    #             tasks.append(tg.create_task(coro))

    #     original_files = [t.result() for t in tasks]
    #     for file in original_files:

    #         # NOTE
    #         # extra case when user copies external Scene (and its Files) more than once
    #         if current_file := await db.files.get_one_or_none(file_id=file.file_id):
    #             logger.warning(
    #                 "Found existing file: %s. "
    #                 "Delete previous file to be replaced with copied one. ",
    #                 current_file.id,
    #             )
    #             await db.files.delete(current_file.id)

    #         logger.warning("Copy file: %s. ", file.id)
    #         await db.files.create(schemas.FileCreate.model_build(file))

    # handle elements:
    ...

    # handle scene
    data = original.model_dump() | payload.model_dump(exclude_unset=True)
    instance = await db.scenes.create(
        schemas.SceneCreate.model_build(**data),
        refresh=True,
    )

    return instance


@scenes.patch("/{scene_id}", status_code=status.HTTP_200_OK)
async def update_scene(
    scene_id: UUID,
    db: DatabaseRepositoriesDepends,
    *,
    schema: schemas.SceneUpdate,
) -> schemas.SceneExtended:
    return await db.scenes.update(scene_id, schema)


@scenes.delete("/{scene_id}", status_code=status.HTTP_200_OK)
async def delete_scene(
    db: DatabaseRepositoriesDepends,
    *,
    scene_id: UUID,
) -> schemas.SceneSimplified:
    """Mark as deleted."""
    return await db.scenes.update(scene_id, is_deleted=True)


########################################################################################
# files
########################################################################################


files = APIRouter(prefix="/files", tags=["Files"], dependencies=[AuthRouterDepends])


@files.get("", status_code=status.HTTP_200_OK)
async def get_file(
    db: DatabaseRepositoriesDepends,
    *,
    file_id: schemas.FileID,
) -> schemas.FileExtended:
    return await db.files.get_one(file_id=file_id)


@files.post("", status_code=status.HTTP_201_CREATED)
async def create_file(
    db: DatabaseRepositoriesDepends,
    logger: LoggerDepends,
    *,
    scene_id: UUID,
    payload: schemas.FileCreate,
) -> schemas.FileSimplified:

    # NOTE: handle multiply requests with the same file from frontend
    if file := await db.files.get_one_or_none(file_id=payload.file_id):
        logger.warning("Duplicate file id: %s. File already exist. ", file.id)
        return file

    return await db.files.create(payload, scene_id=scene_id)
