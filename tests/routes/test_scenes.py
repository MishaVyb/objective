import uuid
from pprint import pprint

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status
from tests.conftest import ClientsFixture
from tests.utils import verbose

from objective.db.models.users import UserModel
from objective.schemas.scenes import SceneCreateSchema, SceneUpdateSchema

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.usefixtures("session"),
]


async def test_scene_crud(
    user: UserModel,
    client: AsyncClient,
    scene_update_request_body: dict,
    app: FastAPI,
) -> None:
    default_scenes_amount = len(app.state.initial_scenes)
    project_id = user.projects[0].id

    # [1] create
    response = await client.post(
        "/api/scenes",
        content=SceneCreateSchema(
            name="test-scene",
            project_id=project_id,
        ).model_dump_json(),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    json = response.json()
    pprint(json)
    scene_id = json["id"]

    # [2] read
    response = await client.get("/api/scenes")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)

    # [2.1] read by id
    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)

    # [2.2] read from project
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    new_scene_index = default_scenes_amount
    assert len(json["scenes"]) == default_scenes_amount + 1
    assert json["scenes"][new_scene_index]["name"] == "test-scene"

    # [3] update simple
    response = await client.patch(
        f"/api/scenes/{scene_id}",
        json=dict(SceneUpdateSchema(name="new-name")),
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    pprint(json)

    assert json["name"] == "new-name"

    # [3.1] update full
    json = json | scene_update_request_body
    response = await client.patch(f"/api/scenes/{scene_id}", json=json)
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()

    assert json["elements"]
    assert json["appState"]

    # [3.3] update partial
    data = {"elements": [{"type": "some-element-type"}]}
    response = await client.patch(
        f"/api/scenes/{scene_id}",
        json=data,
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    pprint(json)

    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert json["name"] == "new-name"
    assert json["appState"]
    assert json["elements"] == [{"type": "some-element-type"}]

    # [4] delete
    response = await client.delete(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    pprint(json)

    # get without filters -- only not deleted
    response = await client.get(f"/api/scenes")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == default_scenes_amount  # only default

    # get from projects
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json["scenes"]) == default_scenes_amount + 1  # both: default and deleted

    # get (with filter)
    response = await client.get(f"/api/scenes", params={"is_deleted": True})
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == 1  # only deleted
    assert json[0]["name"] == "new-name"

    # get (with filter)
    response = await client.get(f"/api/scenes", params={"is_deleted": False})
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert len(json) == len(app.state.initial_scenes)  # only default
    assert json[0]["name"] == app.state.initial_scenes[0].app_state["name"]


async def test_scene_404(clients: ClientsFixture):
    response = await clients.user.get(f"/api/scenes/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND, verbose(response)


async def test_scene_403(clients: ClientsFixture):
    # someone else's scene id:
    id = (await clients.another_user.get("/api/scenes")).json()[0]["id"]

    # read
    # TMP anyone has read access to anything
    response = await clients.user.get(f"/api/scenes/{id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    # update
    response = await clients.user.patch(f"/api/scenes/{id}", json={"name": "name"})
    assert response.status_code == status.HTTP_403_FORBIDDEN, verbose(response)

    # delete
    response = await clients.user.delete(f"/api/scenes/{id}")
    assert response.status_code == status.HTTP_403_FORBIDDEN, verbose(response)


async def test_scene_401(clients: ClientsFixture):
    response = await clients.no_auth.get(f"/api/scenes/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, verbose(response)


# TODO test create scene add file read file delete file


async def test_files_crud(user: UserModel, client: AsyncClient) -> None:
    project_id = user.projects[0].id

    # [1] create scene
    response = await client.post(
        "/api/scenes",
        content=SceneCreateSchema(
            name="test-scene",
            project_id=project_id,
        ).model_dump_json(),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    json = response.json()
    pprint(json)
    scene_id = json["id"]

    # [2] create file
    file_id = "file-id"
    response = await client.post(
        f"/api/scenes/{scene_id}/files",
        json={"id": "file-id", "mimeType": "mimeType", "dataURL": "dataURL"},
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    json = response.json()
    pprint(json)

    assert json == {"id": "file-id", "mimeType": "mimeType"}

    # [3] read at scene
    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)
    assert json["files"] == [{"id": "file-id", "mimeType": "mimeType"}]

    # [3.1] read directly
    response = await client.get(f"/api/scenes/{scene_id}/files/{file_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    pprint(json)
    assert json == {"id": "file-id", "mimeType": "mimeType", "dataURL": "dataURL"}
