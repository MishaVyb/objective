from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from objective.db.dao.scenes import SceneFilters, SceneRepository
from objective.schemas.scenes import (
    SceneCreateSchema,
    SceneReadSchema,
    SceneReadSimplifiedSchema,
    SceneUpdateSchema,
)

router = APIRouter()


@router.get("/scenes", response_model=list[SceneReadSimplifiedSchema])
async def get_scenes(
    filters: Annotated[SceneFilters, Depends()],
    dao: Annotated[SceneRepository, Depends()],
):
    """Get current user scenes."""
    return await dao.get_many(filters)


@router.get("/scenes/{id}", response_model=SceneReadSchema)
async def get_scene(
    id: UUID,
    dao: Annotated[SceneRepository, Depends()],
):
    return await dao.get_one(id)


@router.post(
    "/scenes",
    response_model=SceneReadSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_scene(
    schema: SceneCreateSchema,
    dao: Annotated[SceneRepository, Depends()],
):
    return await dao.create(schema)


@router.patch(
    "/scenes/{id}",
    response_model=SceneReadSchema,
    status_code=status.HTTP_200_OK,
)
async def update_scene(
    id: UUID,
    schema: SceneUpdateSchema,
    dao: Annotated[SceneRepository, Depends()],
):
    return await dao.update(id, schema)


@router.delete(
    "/scenes/{id}",
    response_model=SceneReadSchema,
    status_code=status.HTTP_200_OK,
)
async def delete_scene(
    id: UUID,
    dao: Annotated[SceneRepository, Depends()],
):
    """Mark for delete."""
    return await dao.delete(id)
