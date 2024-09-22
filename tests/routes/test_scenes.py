import logging

import pytest
from dirty_equals import IsDict

from app.applications.objective import ObjectiveAPP
from app.client import ObjectiveClient
from app.schemas import schemas
from tests.helpers import IsPartialSchema
from tests.routes.test_projects import TEST_PROJECT

pytestmark = [
    pytest.mark.anyio,
]


logger = logging.getLogger("conftest")


async def test_scene_crud(app: ObjectiveAPP, client: ObjectiveClient) -> None:
    PROJECT = (await client.get_projects()).items[0]
    ANOTHER_PROJECT = await client.create_project(TEST_PROJECT)

    TEST_SCENE = schemas.SceneCreate(
        name="test-scene",
        project_id=PROJECT.id,
    )
    TEST_SCENE_FULL = schemas.SceneCreate(
        name="test-scene",
        elements=[
            schemas.Element(id="1", file_id="file_1", extra_field_value="value"),
            schemas.Element(id="2", file_id="file_2", extra_field_value="value"),
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
        # files=[], # files not in response, event if it was provided on creation
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

    # [2] update
    # expected = IsPartialSchema(name="upd")
    # payload = schemas.SceneUpdate(name="upd")
    # assert await client.update_scene(scene.id, payload) == expected
    # assert await client.get_scene(scene.id) == expected

    # [2] update full
    payload = schemas.SceneUpdate(
        name="upd-full",
        app_state=schemas.AppState(new_key="new_value"),
        project_id=ANOTHER_PROJECT.id,
    )
    expected = IsPartialSchema(
        name="upd-full",
        # move to another project:
        project=IsPartialSchema(id=ANOTHER_PROJECT.id),
        # full dict replacement:
        app_state=IsDict(new_key="new_value"),
        # does not updated:
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


# TODO
# test copy scene, the same files access able by another user
# test create file twice - ok
# test deleted scene included in project.scenes = [...] always
# test filters


async def test_scene_filters(app: ObjectiveAPP, client: ObjectiveClient) -> None:
    ...


async def test_scene_access_rights(
    app: ObjectiveAPP,
    client: ObjectiveClient,
) -> None:
    ...


async def test_scene_401_404(app: ObjectiveAPP, client: ObjectiveClient) -> None:
    ...
