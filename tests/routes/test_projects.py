from pprint import pprint

import pytest
from httpx import AsyncClient
from starlette import status
from tests.utils import verbose

from objective.db.dao.scenes import ProjectRepository
from objective.schemas.scenes import ProjectCreateSchema, ProjectUpdateSchema

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.usefixtures("session", "user"),
]


async def test_default_project(client: AsyncClient) -> None:
    # [1] get all
    response = await client.get("/api/projects")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)
    assert len(json) == 1
    assert json[0]["name"] == ProjectRepository.DEFAULT_PROJECT_NAME

    # [2] get
    id = json[0]["id"]
    response = await client.get(f"/api/projects/{id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)
    assert json["name"] == ProjectRepository.DEFAULT_PROJECT_NAME


async def test_project_crud(client: AsyncClient) -> None:
    # [1] create
    response = await client.post(
        "/api/projects",
        json=dict(ProjectCreateSchema(name="test-project")),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    json = response.json()
    pprint(json)
    id = json["id"]

    # [2] read
    response = await client.get("/api/projects")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)
    assert len(json) == 2  # default and new one

    # [3] update
    response = await client.patch(
        f"/api/projects/{id}",
        json=dict(ProjectUpdateSchema(name="new-name")),
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    pprint(json)

    response = await client.get(f"/api/projects/{id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert json["name"] == "new-name"

    # [4] delete
    response = await client.delete(f"/api/projects/{id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    pprint(json)

    response = await client.get(f"/api/projects")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == 2  # both: default and deleted

    response = await client.get(f"/api/projects", params={"is_deleted": True})
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == 1  # only deleted
    assert json[0]["name"] == "new-name"

    response = await client.get(f"/api/projects", params={"is_deleted": False})
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == 1  # only default
    assert json[0]["name"] == ProjectRepository.DEFAULT_PROJECT_NAME


async def test_project_access_rights():
    pass


async def test_project_raises():
    pass
