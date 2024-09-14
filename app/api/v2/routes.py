from asyncio import Task, TaskGroup
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.dependencies.users import AuthRouterDepends, AuthUserDepends
from app.exceptions import NotFoundInstanceError
from app.repository import models
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
) -> list[schemas.Project]:
    """Get projects. Apply filters."""
    return await db.projects.get_filter(filters)


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
    schema: schemas.ProjectCreate,
) -> schemas.Project:
    return await db.projects.create(schema)


@projects.patch("/{id}", status_code=status.HTTP_200_OK)
async def update_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
    schema: schemas.ProjectUpdate,
) -> schemas.Project:
    return await db.projects.update(id, schema)


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
) -> list[schemas.SceneExtended]:
    """Get scenes. Apply filters."""
    scenes = await db.scenes.get_filter(filters)
    return [scene for scene in scenes if not scene.project.is_deleted]  # TMP


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
    user: AuthUserDepends,
    *,
    schema: schemas.SceneCreate,
) -> schemas.SceneExtended:
    # TODO move to repository impl
    files = [models.File(created_by_id=user.id, **f.model_dump()) for f in schema.files]
    return await db.scenes.create(schema, refresh=True, files=files)


@scenes.post("/{scene_id}/copy", status_code=status.HTTP_201_CREATED)
async def copy_scene(
    db: DatabaseRepositoriesDepends,
    user: AuthUserDepends,
    *,
    scene_id: UUID,
    schema: schemas.SceneUpdate,  # overrides
) -> schemas.SceneExtended:
    """Duplicate scene. Supports overrides. All scene files are copied too."""

    # TODO move to repository impl
    # REFACTOR !!!!!!!

    original = await db.scenes.get(scene_id)
    orig_schema = schemas.SceneExtended.model_validate(original)

    data = orig_schema.model_dump(exclude_unset=True, exclude={"files"})
    data |= schema.model_dump(exclude_unset=True, exclude={"files"})

    tasks: list[Task[schemas.FileExtended]] = []
    async with TaskGroup() as tg:
        for file in original.files:
            coro = db.files.get_one(scene_id=scene_id, file_id=file.file_id)
            tasks.append(tg.create_task(coro))

    original_files = [t.result() for t in tasks]
    copied_files = [
        # create new file instance which will be attached to new scene by ORM
        # (and set 'create_by' current user)
        models.File(
            **f.model_dump(
                # id / user_id / created_at ...
                exclude=set(schemas.DeclarativeFieldsMixin.model_fields),
            ),
            created_by_id=user.id,
        )
        for f in original_files
    ]
    instance = await db.scenes.create(
        schemas.SceneCreate.model_build(**data),
        files=copied_files,
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


files = APIRouter(prefix="/scenes", tags=["Files"], dependencies=[AuthRouterDepends])


@files.get("/{scene_id}/files/{file_id}", status_code=status.HTTP_200_OK)
async def get_file(
    db: DatabaseRepositoriesDepends,
    logger: LoggerDepends,
    *,
    scene_id: UUID,
    file_id: str,
) -> schemas.FileExtended:
    try:
        return await db.files.get_one(scene_id=scene_id, file_id=file_id)
    except NotFoundInstanceError as e:
        # TMP ugly fix
        # TODO see logs how many scene affected by this problem and write
        # migration script to duplicate those files from other scene to this
        logger.warning(
            f"Not found file per scene: {scene_id}. Fallbacks to all files. ",
        )
        items = await db.files.get_where(file_id=file_id)
        if not items:
            raise e
        return items[0]


@files.post("/{scene_id}/files", status_code=status.HTTP_201_CREATED)
async def create_file(
    db: DatabaseRepositoriesDepends,
    logger: LoggerDepends,
    *,
    scene_id: UUID,
    schema: schemas.FileCreate,
) -> schemas.FileSimplified:
    try:
        # NOTE: handle multiply requests with the same file from frontend
        f = await db.files.get_one(scene_id=scene_id, file_id=schema.file_id)
        logger.warning("Trying to create file, that already exist: %s", f.file_id)
        return f
    except NotFoundInstanceError:
        return await db.files.create(schema, scene_id=scene_id)


# # UNUSED
# # for now its unused on frontend, as we handle delete file by deleting
# # Excalidraw element on frontend, thats all. In future, we could implements deleting
# # files on backend also, if it will be required by getting out of HDD space
# async def delete_file(
#     scene_id: UUID,
#     db: DatabaseRepositoriesDepends,
#     *,
#     file_id: str,
# ) -> schemas.FileSimplified:
#     """Mark as deleted."""
#     instance = await db.files.get(scene_id=scene_id, file_id=file_id)
#     await db.files.delete(instance.id)
#     return instance
