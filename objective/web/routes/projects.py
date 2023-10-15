from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from objective.db.dao.projects import ProjectFilters, ProjectRepository
from objective.schemas.projects import (
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
    """Get current user projects."""
    return await dao.get_many(filters)


@router.get("/projects/{id}", response_model=ProjectReadSchema)
async def get_project(
    id: UUID,
    dao: Annotated[ProjectRepository, Depends()],
):
    return await dao.get_one(id)


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
