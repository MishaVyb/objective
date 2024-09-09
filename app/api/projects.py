from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from starlette import status

from app.dependencies.users import AuthRouterDepends
from app.repository.repositories import DatabaseRepositoriesDepends
from app.schemas import schemas

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
    dependencies=[AuthRouterDepends],
)


class _ProjectFiltersQuery(schemas.ProjectFilters, as_query=True):
    pass


@router.get("")
async def get_projects(
    db: DatabaseRepositoriesDepends,
    *,
    filters: Annotated[_ProjectFiltersQuery, Depends()],
) -> list[schemas.Project]:
    """Get projects. Apply filters."""
    return await db.projects.get_filter(filters)


@router.get("/{id}")
async def get_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
) -> schemas.Project:
    return await db.projects.get(id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    db: DatabaseRepositoriesDepends,
    *,
    schema: schemas.ProjectCreate,
) -> schemas.Project:
    return await db.projects.create(schema)


@router.patch("/{id}", status_code=status.HTTP_200_OK)
async def update_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
    schema: schemas.ProjectUpdate,
) -> schemas.Project:
    return await db.projects.update(id, schema)


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_project(
    db: DatabaseRepositoriesDepends,
    *,
    id: UUID,
) -> schemas.Project:
    """Mark as deleted."""
    return await db.projects.update(id, is_deleted=True)
