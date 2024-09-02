import uuid
from pprint import pprint

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from app.schemas import schemas
from tests_old.conftest import ClientsFixture, UsersFixture
from tests_old.utils import verbose

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.usefixtures("session"),
]


async def test_scene_crud(
    users: UsersFixture,
    client: AsyncClient,
    scene_update_request_body: dict,
    app: FastAPI,
) -> None:
    default_scenes_amount = len(app.state.initial_scenes)
    user = users.user
    another_user = users.another_user
    project_id = user.projects[0].id
    another_project_id = another_user.projects[0].id

    # [1] create
    response = await client.post(
        "/api/scenes",
        content=schemas.SceneCreate(
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
        json=dict(schemas.SceneUpdate(name="new-name")),
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

    # get another project scenes (with filter: project_id and no user)
    response = await client.get(
        f"/api/scenes",
        params={"project_id": str(another_project_id), "user_id": ""},
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert json[0]["user_id"] == str(another_user.id)

    # the same, but omit no user params
    response = await client.get(
        f"/api/scenes",
        params={"project_id": str(another_project_id)},
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    json = response.json()
    assert json == []  # because filtering both project_id & current user by default

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


async def test_scene_crud_with_files(
    users: UsersFixture,
    clients: ClientsFixture,
) -> None:
    user = users.user
    client = clients.user
    project_id = user.projects[0].id

    # [1] create scene
    response = await client.post(
        "/api/scenes",
        content=schemas.SceneCreate(
            name="test-scene",
            project_id=project_id,
            app_state={"key": "value"},
            elements=[{"type": "some-element-type"}],
            files=[
                schemas.FileCreate(
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

    assert scene["user_id"] == str(user.id)
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

    ##################################################
    # [4] copy scene to new project

    # create new project
    response = await client.post(
        "/api/projects",
        json=dict(schemas.ProjectCreate(name="test-project")),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    project_id = response.json()["id"]

    # copy scene (with new name)
    response = await client.post(
        f"/api/scenes/{scene_id}/copy",
        json=schemas.SceneCreate(
            project_id=project_id,
            name="copied",
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    scene = response.json()

    assert scene["id"] != scene_id  # new scene id

    assert scene["user_id"] == str(user.id)
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

    ##################################################
    # [5] copy scene to ANOTHER user's project

    another_client = clients.another_user
    another_user = users.another_user
    project_id = another_user.projects[0].id

    # copy scene (with new name)
    response = await another_client.post(
        f"/api/scenes/{scene_id}/copy",
        json=schemas.SceneCreate(
            project_id=project_id,
            name="copied-to-another-user",
        ).model_dump(mode="json", exclude_unset=True),
    )
    assert response.status_code == status.HTTP_201_CREATED, verbose(response)
    scene = response.json()

    assert scene["id"] != scene_id  # new scene id

    assert scene["user_id"] == str(another_user.id)
    assert scene["name"] == "copied-to-another-user"
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    copied_scene_id = scene["id"]

    # read from projects
    response = await another_client.get(f"/api/projects/{project_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()["scenes"][-1]

    assert scene["user_id"] == str(another_user.id)
    assert scene["name"] == "copied-to-another-user"
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # read by id
    response = await another_client.get(f"/api/scenes/{copied_scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["user_id"] == str(another_user.id)
    assert scene["name"] == "copied-to-another-user"
    assert scene["appState"] == {"key": "value"}  # the same app state
    assert scene["elements"] == [{"type": "some-element-type"}]  # the same elements
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # check file also copied
    response = await another_client.get(
        f"/api/scenes/{copied_scene_id}/files/{file_id}",
    )
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    file = response.json()
    assert file == {"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"}

    ##################################################
    # [6] final check: original scene files was not affected (!)

    response = await client.get(f"/api/scenes/{scene_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    scene = response.json()

    assert scene["user_id"] == str(user.id)
    assert scene["name"] == "test-scene"
    assert scene["files"] == [
        {"id": "initial-file-id", "mimeType": "mimeType"},
        {"id": "new-file-id", "mimeType": "mimeType"},
    ]

    # check get original file
    response = await client.get(f"/api/scenes/{scene_id}/files/{file_id}")
    assert response.status_code == status.HTTP_200_OK, verbose(response)
    file = response.json()
    assert file == {"id": "new-file-id", "mimeType": "mimeType", "dataURL": "dataURL"}
