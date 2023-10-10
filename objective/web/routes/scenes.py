from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from objective.db.dao.scenes import ProjectFilters, ProjectRepository
from objective.schemas.scenes import (
    ProjectCreateSchema,
    ProjectReadSchema,
    ProjectUpdateSchema,
)

router = APIRouter()


@router.get("/projects", response_model=list[ProjectReadSchema])
async def get_projects(
    filters: Annotated[ProjectFilters, Depends()],
    dao: Annotated[ProjectRepository, Depends()],
):
    return await dao.get_all(filters)


@router.get("/projects/{id}", response_model=ProjectReadSchema)
async def get_project(
    id: UUID,
    dao: Annotated[ProjectRepository, Depends()],
):
    instance = await dao.get(id)
    if not instance:
        raise HTTPException(status_code=404, detail="Not found")
    return instance


@router.post(
    "/projects",
    response_model=ProjectReadSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    schema: ProjectCreateSchema,
    dao: Annotated[ProjectRepository, Depends()],
):
    return await dao.create(schema)


@router.patch(
    "/projects/{id}",
    response_model=ProjectReadSchema,
    status_code=status.HTTP_200_OK,
)
async def update_project(
    id: UUID,
    schema: ProjectUpdateSchema,
    dao: Annotated[ProjectRepository, Depends()],
):
    return await dao.update(id, schema)


@router.delete(
    "/projects/{id}",
    response_model=ProjectReadSchema,
    status_code=status.HTTP_200_OK,
)
async def delete_project(
    id: UUID,
    dao: Annotated[ProjectRepository, Depends()],
):
    """Mark for delete."""
    return await dao.delete(id)
