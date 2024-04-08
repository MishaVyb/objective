from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from objective.db.dao.scenes import FileRepository, SceneFilters, SceneRepository
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

router = APIRouter()


@router.get("/scenes", response_model=list[SceneExtendedReadSchema])
async def get_scenes(
    filters: Annotated[SceneFilters, Depends()],
    dao: Annotated[SceneRepository, Depends()],
):
    """Get current user scenes."""
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
    return await dao.create(schema)


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
    dao: Annotated[FileRepository, Depends()],
):
    return await dao.get_one_where(scene_id=scene_id, file_id=file_id)


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
