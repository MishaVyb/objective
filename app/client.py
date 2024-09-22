from http import HTTPMethod
from uuid import UUID

from app.schemas import schemas
from common.async_client import HTTPXClientBase


class ObjectiveClient(HTTPXClientBase):
    _api_prefix = "/api/v2/"

    async def get_projects(
        self,
        filters: schemas.ProjectFilters | None = None,
    ) -> schemas.GetProjectsResponse:
        return await self._call_service(
            HTTPMethod.GET,
            "/projects",
            params=filters,
            response_schema=schemas.GetProjectsResponse,
        )

    async def get_project(self, id: UUID) -> schemas.Project:
        return await self._call_service(
            HTTPMethod.GET,
            f"/projects/{id}",
            response_schema=schemas.Project,
        )

    async def create_project(self, payload: schemas.ProjectCreate) -> schemas.Project:
        return await self._call_service(
            HTTPMethod.POST,
            "/projects",
            payload=payload,
            response_schema=schemas.Project,
        )

    async def update_project(
        self,
        id: UUID,
        payload: schemas.ProjectUpdate,
    ) -> schemas.Project:
        return await self._call_service(
            HTTPMethod.POST,
            f"/projects/{id}",
            payload=payload,
            response_schema=schemas.Project,
        )

    async def delete_project(self, id: UUID) -> schemas.Project:
        """Mark as deleted."""
        return await self._call_service(
            HTTPMethod.POST,
            f"/projects/{id}",
            response_schema=schemas.Project,
        )
