from http import HTTPMethod
from uuid import UUID

from app.schemas import schemas
from common.async_client import HTTPXClientBase


class ObjectiveClient(HTTPXClientBase):
    _api_prefix = "/api/v2/"

    ########################################################################################
    # users
    ########################################################################################

    async def get_user_me(self) -> schemas.User:
        return await self._call_service(
            HTTPMethod.GET,
            f"/users/me",
            response_schema=schemas.User,
        )

    ########################################################################################
    # projects
    ########################################################################################

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
            HTTPMethod.PATCH,
            f"/projects/{id}",
            payload=payload,
            response_schema=schemas.Project,
        )

    async def delete_project(self, id: UUID) -> schemas.Project:
        """Mark as deleted."""
        return await self._call_service(
            HTTPMethod.DELETE,
            f"/projects/{id}",
            response_schema=schemas.Project,
        )

    ########################################################################################
    # scenes
    ########################################################################################

    async def get_scenes(
        self,
        filters: schemas.SceneFilters | None = None,
    ) -> schemas.GetScenesResponse:
        return await self._call_service(
            HTTPMethod.GET,
            "/scenes",
            params=filters,
            response_schema=schemas.GetScenesResponse,
        )

    async def get_scene(self, id: UUID) -> schemas.SceneExtended:
        return await self._call_service(
            HTTPMethod.GET,
            f"/scenes/{id}",
            response_schema=schemas.SceneExtended,
        )

    async def create_scene(self, payload: schemas.SceneCreate) -> schemas.SceneExtended:
        return await self._call_service(
            HTTPMethod.POST,
            "/scenes",
            payload=payload,
            response_schema=schemas.SceneExtended,
        )

    async def update_scene(
        self,
        id: UUID,
        payload: schemas.SceneUpdate,
    ) -> schemas.SceneExtended:
        return await self._call_service(
            HTTPMethod.PATCH,
            f"/scenes/{id}",
            payload=payload,
            response_schema=schemas.SceneExtended,
        )

    async def delete_scene(self, id: UUID) -> schemas.SceneSimplified:
        """Mark as deleted."""
        return await self._call_service(
            HTTPMethod.DELETE,
            f"/scenes/{id}",
            response_schema=schemas.SceneSimplified,
        )

    ########################################################################################
    # files
    ########################################################################################

    async def get_file(self, file_id: schemas.FileID) -> schemas.FileExtended:
        return await self._call_service(
            HTTPMethod.GET,
            f"/files/{file_id}",
            response_schema=schemas.FileExtended,
        )

    async def create_file(self, payload: schemas.FileCreate) -> schemas.FileSimplified:
        return await self._call_service(
            HTTPMethod.POST,
            "/files",
            payload=payload,
            response_schema=schemas.FileSimplified,
        )
