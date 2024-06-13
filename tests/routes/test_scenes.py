import uuid
from pprint import pprint

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status
from tests.conftest import ClientsFixture
from tests.utils import verbose

from objective.db.models.users import UserModel
from objective.schemas.projects import ProjectCreateSchema
from objective.schemas.scenes import (
    FileCreateSchema,
    SceneCreateSchema,
    SceneUpdateSchema,
)

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
    scene = response.json()[-1]

    assert scene["name"] == "test-scene"
    assert scene["appState"] == {}
    assert scene["elements"] == []

    # [2.1] read by id
    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["name"] == "test-scene"
    assert scene["appState"] == {}
    assert scene["elements"] == []

    # [2.2] read from project
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)

    json = response.json()
    assert len(json["scenes"]) == default_scenes_amount + 1
    scene = json["scenes"][-1]

    assert scene["name"] == "test-scene"
    assert "appState" not in scene
    assert "elements" not in scene

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


async def test_scene_crud_with_files(user: UserModel, client: AsyncClient) -> None:
    project_id = user.projects[0].id

    # [1] create scene
    response = await client.post(
        "/api/scenes",
        content=SceneCreateSchema(
            name="test-scene",
            project_id=project_id,
            app_state={"key": "value"},
            elements=[{"type": "some-element-type"}],
            files=[
                FileCreateSchema(
                    file_id="initial-file-id",
                    type="mimeType",
                    data="dataURL",
                ),
            ],
        ).model_dump_json(),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    scene = response.json()
    scene_id = scene["id"]

    # read by id
    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["name"] == "test-scene"
    assert scene["appState"] == {"key": "value"}
    assert scene["elements"] == [{"type": "some-element-type"}]
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
    ]

    # [2] create file
    file_id = "new-file-id"
    response = await client.post(
        f"/api/scenes/{scene_id}/files",
        json={"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"},
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)

    # [2.1] create files twice -- OK (skip error silently)
    response = await client.post(
        f"/api/scenes/{scene_id}/files",
        json={"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"},
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    file = response.json()
    assert file == {"id": "new-file-id", "mimeType": "mimeType"}

    # [3] read at scene
    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # [3.1] read directly
    response = await client.get(f"/api/scenes/{scene_id}/files/{file_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    file = response.json()

    assert file == {"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"}

    # [4] copy scene to new project

    # create new project
    response = await client.post(
        "/api/projects",
        json=dict(ProjectCreateSchema(name="test-project")),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    project_id = response.json()["id"]

    # copy scene (with new name)
    response = await client.post(
        f"/api/scenes/{scene_id}/copy",
        json=SceneCreateSchema(
            project_id=project_id,
            name="copied",
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    scene = response.json()

    assert scene["id"] != scene_id  # new scene id
    assert scene["name"] == "copied"
    # NOTE: the same file ids, but it's another record in database as it stored under ../scene_id/file_id
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    copied_scene_id = scene["id"]

    # read from projects
    response = await client.get(f"/api/projects/{project_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()["scenes"][-1]

    assert scene["name"] == "copied"
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # read by id
    response = await client.get(f"/api/scenes/{copied_scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["name"] == "copied"
    assert scene["appState"] == {"key": "value"}  # the same app state
    assert scene["elements"] == [{"type": "some-element-type"}]  # the same elements
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # check file also copied
    response = await client.get(f"/api/scenes/{copied_scene_id}/files/{file_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    file = response.json()
    assert file == {"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"}
