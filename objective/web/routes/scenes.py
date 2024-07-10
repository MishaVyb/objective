import logging
from asyncio import Task, TaskGroup
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from objective.db.dao.scenes import FileRepository, SceneFilters, SceneRepository
from objective.db.models.scenes import FileModel
from objective.db.models.users import UserModel
from objective.schemas.base import BaseReadSchema
from objective.schemas.scenes import (
    FileBaseSchema,
    FileCreateSchema,
    FileExtendedSchema,
    GetSceneResponse,
    SceneCreateSchema,
    SceneExtendedReadSchema,
    SceneSimplifiedReadSchema,
    SceneUpdateSchema,
    UpdateSceneResponse,
)
from objective.web.dependencies import current_active_user
from objective.web.exceptions import NotFoundError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scenes", response_model=list[SceneExtendedReadSchema])
async def get_scenes(
    filters: Annotated[SceneFilters, Depends()],
    dao: Annotated[SceneRepository, Depends()],
):
    """Get scenes. Apply filters."""
    scenes = await dao.get_many(filters)
    return [scene for scene in scenes if not scene.project.is_deleted]  # TMP


@router.get("/scenes/{scene_id}", response_model=GetSceneResponse)
async def get_scene(
    scene_id: UUID,
    dao: Annotated[SceneRepository, Depends()],
):
    return await dao.get_one(scene_id)


@router.post(
    "/scenes",
    response_model=SceneSimplifiedReadSchema,  # TODO remove returning heavy data on scene updating / deleting / creating as we do not need it, only meta info
    status_code=status.HTTP_201_CREATED,
)
async def create_scene(
    schema: SceneCreateSchema,
    dao: Annotated[SceneRepository, Depends()],
):
    files = [
        FileModel(
            user_id=dao.user.id,
            **f.model_dump(),
        )
        for f in schema.files
    ]
    return await dao.create(schema, files=files)


@router.post(
    "/scenes/{scene_id}/copy",
    response_model=SceneSimplifiedReadSchema,  # TODO remove returning heavy data on scene updating / deleting / creating as we do not need it, only meta info
    status_code=status.HTTP_201_CREATED,
)
async def copy_scene(
    scene_id: UUID,
    schema: SceneUpdateSchema,  # overrides
    user: Annotated[UserModel, Depends(current_active_user)],
    dao_scenes: Annotated[SceneRepository, Depends()],
    dao_files: Annotated[FileRepository, Depends()],
):
    """Duplicate scene. Supports overrides. All scene files are copied too."""

    original = await dao_scenes.get_one(scene_id)
    orig_schema = SceneExtendedReadSchema.model_validate(original)

    data = orig_schema.model_dump(exclude_unset=True, exclude={"files"})
    data |= schema.model_dump(exclude_unset=True, exclude={"files"})

    tasks: list[Task[FileModel]] = []
    async with TaskGroup() as tg:
        for file in original.files:
            coro = dao_files.get_one_where(scene_id=scene_id, file_id=file.file_id)
            tasks.append(tg.create_task(coro))

    original_files = [t.result() for t in tasks]
    copied_files = [
        # create new file instance which will be attached to new scene by ORM
        # (and set 'create_by' current user)
        FileModel(
            **f.to_dict(
                # id / user_id / created_at ...
                exclude=set(BaseReadSchema.model_fields),
            ),
            user_id=user.id,
        )
        for f in original_files
    ]
    instance = await dao_scenes.create(SceneCreateSchema(**data), files=copied_files)
    return instance


@router.patch(
    "/scenes/{scene_id}",
    status_code=status.HTTP_200_OK,
    response_model=UpdateSceneResponse,  # TODO remove returning heavy data on scene updating / deleting / creating as we do not need it, only meta info
)
async def update_scene(
    scene_id: UUID,
    schema: SceneUpdateSchema,
    dao: Annotated[SceneRepository, Depends()],
):
    return await dao.update(scene_id, schema)


@router.delete(
    "/scenes/{scene_id}",
    response_model=SceneSimplifiedReadSchema,  # TODO remove returning heavy data on scene updating / deleting / creating as we do not need it, only meta info
    status_code=status.HTTP_200_OK,
)
async def delete_scene(
    scene_id: UUID,
    dao: Annotated[SceneRepository, Depends()],
):
    """Mark for delete."""
    return await dao.delete(scene_id)


@router.get("/scenes/{scene_id}/files/{file_id}", response_model=FileExtendedSchema)
async def get_file(
    scene_id: UUID,
    file_id: str,
    user: Annotated[UserModel, Depends(current_active_user)],
    dao: Annotated[FileRepository, Depends()],
):
    try:
        return await dao.get_one_where(scene_id=scene_id, file_id=file_id)
    except NotFoundError as e:
        # TMP ugly fix
        # TODO see logs how many scene affected by this problem and write
        # migration script to duplicate those files from other scene to this
        logger.warning(
            f"Not found file per scene: {scene_id}. Fallbacks to all files. ",
        )
        items = await dao.get_where(file_id=file_id)
        if not items:
            raise e
        return items[0]


@router.post(
    "/scenes/{scene_id}/files",
    response_model=FileBaseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_file(
    scene_id: UUID,
    schema: FileCreateSchema,
    dao: Annotated[FileRepository, Depends()],
):
    try:
        # NOTE: handle multiply requests with the same file from frontend
        f = await dao.get_one_where(scene_id=scene_id, file_id=schema.file_id)
        logger.warning("Trying to create file, that already exist: %s", f.file_id)
        return f
    except NotFoundError:
        return await dao.create(schema, scene_id=scene_id)


# UNUSED
# for now its unused on frontend, as we handle delete file by deleting
# Excalidraw element on frontend, thats all. In future, we could implements deleting
# files on backend also, if it will be required by getting out of HDD space
@router.delete("/scenes/{scene_id}/files/{file_id}", response_model=FileBaseSchema)
async def delete_file(
    scene_id: UUID,
    file_id: str,
    dao: Annotated[FileRepository, Depends()],
):
    """Mark for delete."""
    instance = await dao.get_one_where(scene_id=scene_id, file_id=file_id)
    await dao.delete(instance.id)
    return instance
