import logging
import uuid

import pytest
from dirty_equals import IsDict, IsStr
from fastapi import HTTPException, status

from app.client import ObjectiveClient
from app.exceptions import NotFoundInstanceError
from app.schemas import schemas
from common.fastapi.exceptions.exceptions import NotEnoughRights
from tests.helpers import IsList, IsPartialSchema
from tests.routes.test_projects import TEST_PROJECT

pytestmark = [
    pytest.mark.anyio,
]


logger = logging.getLogger("conftest")

ELEMENT = schemas.Element(
    id="1",
    is_deleted=False,
    seed=1,
    version=1,
    version_nonce=1,
    updated=1,
)


async def test_scene_crud(client: ObjectiveClient) -> None:
    PROJECT = (await client.get_projects()).items[0]
    ANOTHER_PROJECT = await client.create_project(TEST_PROJECT)

    TEST_SCENE = schemas.SceneCreate(
        name="test-scene",
        project_id=PROJECT.id,
    )
    TEST_SCENE_FULL = schemas.SceneCreate(
        name="test-scene",
        elements=[
            ELEMENT.model_remake(id="1", file_id="file_1", extra_field_value="value"),
            ELEMENT.model_remake(id="2", file_id="file_2", extra_field_value="value"),
        ],
        app_state=schemas.AppState(extra_field_value="value"),
        files=[
            schemas.FileCreate(id="file_1", data="data_1", type="image/png"),
            schemas.FileCreate(id="file_2", data="data_2", type="image/png"),
        ],
        project_id=PROJECT.id,
    )

    # [1] create
    expected = IsPartialSchema(
        name=TEST_SCENE.name,
    )
    scene = await client.create_scene(TEST_SCENE)
    assert scene == expected
    scene = await client.get_scene(scene.id)
    assert scene == expected

    results = await client.get_scenes()
    assert results.items == [
        IsPartialSchema(),  # default
        IsPartialSchema(),  # default
        IsPartialSchema(name=TEST_SCENE.name),
    ]

    # [1.2] create from '.objective' file
    expected = IsPartialSchema(
        name=TEST_SCENE_FULL.name,
        elements=[
            IsPartialSchema(id="1", extra_field_value="value"),
            IsPartialSchema(id="2", extra_field_value="value"),
        ],
        app_state=IsPartialSchema(extra_field_value="value"),
        project=IsPartialSchema(id=PROJECT.id),
        # files=[], # files not in response, even if it was provided on creation
    )
    scene = await client.create_scene(TEST_SCENE_FULL)
    assert scene == expected
    scene = await client.get_scene(scene.id)
    assert scene == expected

    # getting files by separate requests
    result = [
        await client.get_file("file_1"),
        await client.get_file("file_2"),
    ]
    expected = [
        IsPartialSchema(id="file_1", data="data_1"),
        IsPartialSchema(id="file_2", data="data_2"),
    ]
    assert result == expected

    # [2] update partial
    expected = IsPartialSchema(name="upd")
    payload = schemas.SceneUpdate(name="upd")
    assert await client.update_scene(scene.id, payload) == expected
    assert await client.get_scene(scene.id) == expected

    # [2] update full
    payload = schemas.SceneUpdate(
        name="upd-full",
        app_state=schemas.AppState(new_key="new_value"),
        project_id=ANOTHER_PROJECT.id,
    )
    expected = IsPartialSchema(
        name="upd-full",
        # moved to another project:
        project=IsPartialSchema(id=ANOTHER_PROJECT.id),
        # AppState was fully replaced:
        app_state=IsDict(new_key="new_value"),
        # elements was not updated:
        elements=[
            IsPartialSchema(id="1", extra_field_value="value"),
            IsPartialSchema(id="2", extra_field_value="value"),
        ],
    )
    assert await client.update_scene(scene.id, payload) == expected
    assert await client.get_scene(scene.id) == expected

    # [3] delete
    result = await client.delete_scene(scene.id)
    assert result == IsPartialSchema(name="upd-full", is_deleted=True)

    # [4] recover
    result = await client.update_scene(scene.id, schemas.SceneUpdate(is_deleted=False))
    assert result == IsPartialSchema(name="upd-full", is_deleted=False)


async def test_scene_copy(
    CLIENT_A: ObjectiveClient,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT = (await CLIENT_B.get_projects()).items[0]
    SCENE = (await CLIENT_B.get_scenes()).items[0]
    ANOTHER_PROJECT = await CLIENT_B.create_project(TEST_PROJECT)
    ANOTHER_USER_PROJECT = (await CLIENT_A.get_projects()).items[0]
    ANOTHER_USER_SCENE = (await CLIENT_A.get_scenes()).items[0]

    # [1] copy
    payload = schemas.SceneUpdate(name="copy")
    result = await CLIENT_B.copy_scene(SCENE.id, payload)
    assert result.id != SCENE.id
    assert result == IsPartialSchema(
        payload,
        project=IsPartialSchema(id=PROJECT.id),
        elements=IsList(length=(1, ...)),
    )

    # [2] copy and move
    payload = schemas.SceneUpdate(name="copy", project_id=ANOTHER_PROJECT.id)
    result = await CLIENT_B.copy_scene(SCENE.id, payload)
    assert result.id != SCENE.id
    assert result == IsPartialSchema(
        name=payload.name,
        project=IsPartialSchema(id=ANOTHER_PROJECT.id),
        elements=IsList(length=(1, ...)),
    )

    # [3] copy another User scene to self project
    payload = schemas.SceneUpdate(name="copy", project_id=PROJECT.id)
    result = await CLIENT_B.copy_scene(ANOTHER_USER_SCENE.id, payload)
    assert result.id != SCENE.id
    assert result == IsPartialSchema(
        name=payload.name,
        project=IsPartialSchema(id=PROJECT.id),
        elements=IsList(length=(1, ...)),
    )

    # files from copied scene are not copied itself (both scenes using the same files / db records)
    initial_scene_file_ids = [
        element.file_id for element in ANOTHER_USER_SCENE.elements if element.file_id
    ]
    copied_scene_file_ids = [
        element.file_id for element in result.elements if element.file_id
    ]
    assert initial_scene_file_ids == copied_scene_file_ids

    # scene files accessible even after copy
    for file_id in copied_scene_file_ids:
        res = await CLIENT_B.get_file(file_id)
        assert res == IsPartialSchema(
            data=IsStr(min_length=10),
            #
            # and files is created by initial user, who send those file for the first time
            created_by_id=ANOTHER_USER_PROJECT.created_by_id,
        )


async def test_files_crud(client: ObjectiveClient) -> None:
    # NOTE
    # - files could be created via Scene create/copy, that tested above
    # - and files could be created directly

    payload = schemas.FileCreate(id="file_1", data="data_1", type="image/png")
    assert await client.create_file(payload) == IsPartialSchema(id="file_1")
    assert await client.get_file("file_1") == IsPartialSchema(payload)

    # create the same file twice -- ok
    assert await client.create_file(payload) == IsPartialSchema(id="file_1")


async def test_scene_filters_is_deleted(client: ObjectiveClient) -> None:
    # arrange:
    PROJECT = (await client.get_projects()).items[0]
    await client.delete_scene(PROJECT.scenes[0].id)

    # act:
    results = await client.get_scenes()
    assert results.items == [
        IsPartialSchema(is_deleted=True),
        IsPartialSchema(is_deleted=False),
    ]
    results = await client.get_scenes(schemas.SceneFilters(is_deleted=False))
    assert results.items == [
        # IsPartialSchema(is_deleted=True),
        IsPartialSchema(is_deleted=False),
    ]
    results = await client.get_scenes(schemas.SceneFilters(is_deleted=True))
    assert results.items == [
        IsPartialSchema(is_deleted=True),
        # IsPartialSchema(is_deleted=False),
    ]

    # project has always both DELETED and NOT DELETED scenes
    result = await client.get_project(PROJECT.id)
    assert result.scenes == [
        IsPartialSchema(is_deleted=True),
        IsPartialSchema(is_deleted=False),
    ]
    result = (
        await client.get_projects(schemas.ProjectFilters(is_deleted=False))
    ).items[0]
    assert result.scenes == [
        IsPartialSchema(is_deleted=True),
        IsPartialSchema(is_deleted=False),
    ]


async def test_scene_filters_project_id(
    client: ObjectiveClient,
    *,
    USER_A: schemas.User,
    CLIENT_A: ObjectiveClient,
    USER_B: schemas.User,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]

    results = await CLIENT_A.get_scenes(schemas.SceneFilters(created_by_id=USER_B.id))
    assert results.items == [
        IsPartialSchema(created_by_id=USER_B.id),
        IsPartialSchema(created_by_id=USER_B.id),
    ]
    results = await CLIENT_A.get_scenes(schemas.SceneFilters(created_by_id=""))
    assert results.items == [
        IsPartialSchema(created_by_id=USER_A.id),
        IsPartialSchema(created_by_id=USER_A.id),
        IsPartialSchema(created_by_id=USER_B.id),
        IsPartialSchema(created_by_id=USER_B.id),
    ]

    # per project
    results = await CLIENT_A.get_scenes(
        schemas.SceneFilters(created_by_id="", project_id=PROJECT_B.id),
    )
    assert results.items == [
        IsPartialSchema(created_by_id=USER_B.id),
        IsPartialSchema(created_by_id=USER_B.id),
    ]
    # per project, created by current_user by default
    results = await CLIENT_A.get_scenes(schemas.SceneFilters(project_id=PROJECT_B.id))
    assert results.items == []  # no results


async def test_scene_access_rights(
    *,
    USER_A: schemas.User,
    CLIENT_A: ObjectiveClient,
    USER_B: schemas.User,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]

    # TMP anyone has read access to anything
    result = await CLIENT_A.get_project(PROJECT_B.id)
    assert result == IsPartialSchema(created_by_id=USER_B.id)

    # update/delete
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(
            PROJECT_B.scenes[0].id,
            schemas.SceneUpdate(name="upd"),
        )
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_scene(PROJECT_B.scenes[0].id)

    # create scene with another user project
    payload = schemas.SceneCreate(name="name", project_id=PROJECT_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.create_scene(payload)

    # copy self scene to another user project
    payload = schemas.SceneUpdate(name="copy", project_id=PROJECT_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.copy_scene(PROJECT_A.scenes[0].id, payload)

    # sync elements
    # TODO


async def test_scene_401(setup_clients: dict[str | int, ObjectiveClient]):
    with pytest.raises(HTTPException) as exc:
        await setup_clients["unauthorized"].get_scene(uuid.uuid4())
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


async def test_scene_404(client: ObjectiveClient):
    with pytest.raises(NotFoundInstanceError):
        await client.get_project(uuid.uuid4())
