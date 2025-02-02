import logging
import uuid
from asyncio import TaskGroup

import pytest
from dirty_equals import AnyThing, IsDict, IsStr
from fastapi import HTTPException, status

from app.client import ObjectiveClient
from app.exceptions import NotFoundInstanceError
from app.schemas import schemas
from common.fastapi.exceptions.exceptions import NotEnoughRights
from tests.conftest_data import ExcalidrawElement
from tests.helpers import IsList, IsPartialSchema
from tests.routes.test_projects import TEST_PROJECT

pytestmark = [
    pytest.mark.anyio,
]


logger = logging.getLogger("conftest")


async def test_scene_crud(client: ObjectiveClient) -> None:
    PROJECT = (await client.get_projects()).items[0]
    ANOTHER_PROJECT = await client.create_project(TEST_PROJECT)

    TEST_SCENE = schemas.SceneCreate(
        name="test-scene",
        project_id=PROJECT.id,
    )
    TEST_SCENE_FROM_FILE = schemas.SceneCreate(
        name="test-scene",
        elements=[
            ExcalidrawElement(id="1", file_id="file_1", extra_field_value="value"),
            ExcalidrawElement(id="2", file_id="file_2", extra_field_value="value"),
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
        name=TEST_SCENE_FROM_FILE.name,
        elements=[
            IsPartialSchema(id="1", extra_field_value="value"),
            IsPartialSchema(id="2", extra_field_value="value"),
        ],
        app_state=IsPartialSchema(extra_field_value="value"),
        project=IsPartialSchema(id=PROJECT.id),
        # files=[], # files not in response, even if it was provided on creation
    )

    # getting scene by direct request
    scene = await client.create_scene(TEST_SCENE_FROM_FILE)
    assert scene == expected
    scene = await client.get_scene(scene.id)
    assert scene == expected

    # getting scene from project request
    project = (await client.get_projects()).items[0]
    assert project.scenes[-1] == IsPartialSchema(
        name=TEST_SCENE_FROM_FILE.name,
        app_state=IsPartialSchema(extra_field_value="value"),
        type=AnyThing,
        version=AnyThing,
        source=AnyThing,
    )

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


async def test_scene_elements_crud(
    CLIENT: ObjectiveClient,
    PROJECT: schemas.Project,
) -> None:
    TEST_SCENE_FULL = schemas.SceneCreate(
        name="test-scene",
        elements=[
            ExcalidrawElement(id="element_1"),
            ExcalidrawElement(id="element_2"),
        ],
        app_state=schemas.AppState(),
        files=[],
        project_id=PROJECT.id,
    )
    SCENE = await CLIENT.create_scene(TEST_SCENE_FULL)

    ########################################################################################
    # [1] append new els
    ########################################################################################

    el_3 = ExcalidrawElement(id="element_3")
    el_4 = ExcalidrawElement(id="element_4")
    expected_els = [  # only previous elements which NEW for client
        IsPartialSchema(id="element_1"),
        IsPartialSchema(id="element_2"),
    ]
    r = await CLIENT.reconcile_els(SCENE.id, [el_3, el_4])
    assert r.items == expected_els
    assert (st := r.next_sync_token)

    # request all elements from the beginning
    expected_els = [
        IsPartialSchema(id="element_1"),
        IsPartialSchema(id="element_2"),
        IsPartialSchema(id="element_3"),
        IsPartialSchema(id="element_4"),
    ]
    r = await CLIENT.get_els(SCENE.id)
    assert r.items == expected_els

    # request elements after prev sync
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == []

    ########################################################################################
    # [2] update els
    # - check merge updated depending on 'updated', NOT 'version'
    ########################################################################################

    el_4_updated_A = (
        # this update A has higher 'version',
        # but it would be omitted, because it has been made before next update B
        el_4.model_copy()
        .update(key="UPDATE_1_B")
        .update(key="UPDATE_2_B")
        .update(key="UPDATE_3_B")
    )
    el_4_updated_B = el_4.model_copy().update(key="UPDATE_1_A")

    el_3_updated_C = el_3.model_copy().update(key="UPDATE_1_C")
    el_4_updated_C = el_4.model_copy().update(key="UPDATE_1_C")

    r = await CLIENT.reconcile_els(SCENE.id, [el_4_updated_B], sync_token=st)
    assert r.items == []

    # check el update has been applied
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == [IsPartialSchema(id="element_4", key="UPDATE_1_A")]

    # [2.2] send the same update again
    # update would be ignored because of the same 'version_nonce'
    el_4_updated_B.key = "NOT_PROPER_UPDATE_VALUE"
    r = await CLIENT.reconcile_els(SCENE.id, [el_4_updated_B], sync_token=st)
    assert r.items == []

    # check update has NOT been taken
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == [IsPartialSchema(id="element_4", key="UPDATE_1_A")]

    # [2.3] send update A for the same element that was made earlier than update B
    r = await CLIENT.reconcile_els(SCENE.id, [el_4_updated_A], sync_token=st)
    assert r.items == [IsPartialSchema(id="element_4", key="UPDATE_1_A")]

    # check update has NOT been taken
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == [IsPartialSchema(id="element_4", key="UPDATE_1_A")]

    # [2.3] send update C -- would be taken fully
    r = await CLIENT.reconcile_els(
        SCENE.id,
        [el_3_updated_C, el_4_updated_C],
        sync_token=st,
    )
    assert r.items == []

    # check el update has been applied
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == [
        IsPartialSchema(id="element_3", key="UPDATE_1_C"),
        IsPartialSchema(id="element_4", key="UPDATE_1_C"),
    ]

    ########################################################################################
    # [3] update & create
    ########################################################################################

    el_4_updated_D = el_4.model_copy().update(key="UPDATE_1_D")
    el_5 = ExcalidrawElement(id="element_5")
    r = await CLIENT.reconcile_els(SCENE.id, [el_4_updated_D, el_5], sync_token=st)
    assert r.items == [
        IsPartialSchema(id="element_3", key="UPDATE_1_C"),  # from prev update request
    ]

    # check el update has been applied
    r = await CLIENT.get_els(SCENE.id, sync_token=st)
    assert r.items == IsList(
        IsPartialSchema(id="element_3", key="UPDATE_1_C"),
        IsPartialSchema(id="element_4", key="UPDATE_1_D"),
        IsPartialSchema(id="element_5"),
        check_order=False,
    )


async def test_scene_elements_next_sync_token_simple(
    CLIENT_A: ObjectiveClient,
    SCENE: schemas.SceneExtended,
) -> None:
    """
    Next sync token filters against **database** '_updated' field (not client).

    Expecting elements to sync from server, even if it was created EARLIER than last
    client request, but it was stored at db AFTER that last sync request.
    """
    el_6 = ExcalidrawElement(id="element_6")

    r = await CLIENT_A.reconcile_els(SCENE.id)
    assert (sync_token := r.next_sync_token)

    # another client append el 6
    await CLIENT_A.reconcile_els(SCENE.id, [el_6])

    # re-fetch from prev sync_token
    r = await CLIENT_A.reconcile_els(SCENE.id, sync_token=sync_token)
    assert r.items == [
        IsPartialSchema(id="element_6"),
    ]


async def test_scene_elements_next_sync_token_lock_scene(
    CLIENT: ObjectiveClient,
    SCENE: schemas.SceneExtended,
) -> None:
    """
    Updates for one scene happened one after another.
    """
    el_1 = ExcalidrawElement(id="element_1")
    el_2 = ExcalidrawElement(id="element_2")

    async with TaskGroup() as group:
        coro1 = CLIENT.reconcile_els(SCENE.id, [el_1])
        coro2 = CLIENT.reconcile_els(SCENE.id, [el_2])
        t1 = group.create_task(coro1)
        t2 = group.create_task(coro2)

    res_1 = t1.result()
    res_2 = t2.result()

    # res_2 already has updates 1 because it has been wait for scene would be released
    # (because of Lock)
    assert res_1.items == []
    assert res_2.items == [IsPartialSchema(el_1)]

    # later res_1 sync token could be used to get update 2
    result = await CLIENT.reconcile_els(SCENE.id, sync_token=res_1.next_sync_token)
    assert result.items == [IsPartialSchema(el_2)]

    result = await CLIENT.reconcile_els(SCENE.id, sync_token=res_2.next_sync_token)
    assert result.items == []


async def test_scene_elements_next_sync_token_no_lock_scene(
    CLIENT: ObjectiveClient,
    SCENE: schemas.SceneExtended,
    SCENE_2: schemas.SceneExtended,
) -> None:
    """
    Updates for different scenes happened simultaneity.
    """
    el = ExcalidrawElement(id="element")

    async with TaskGroup() as group:
        coro1 = CLIENT.reconcile_els(SCENE.id, [el])
        coro2 = CLIENT.reconcile_els(SCENE_2.id, [el])
        t1 = group.create_task(coro1)
        t2 = group.create_task(coro2)

    res_1 = t1.result()
    res_2 = t2.result()
    ...


async def test_scene_elements_next_sync_token_no_lock_for_get_request(
    CLIENT: ObjectiveClient,
    SCENE: schemas.SceneExtended,
) -> None:
    """
    Update/Read for one scene happened simultaneously. No lock.
    """
    el = ExcalidrawElement(id="element")
    async with TaskGroup() as group:
        coro1 = CLIENT.reconcile_els(SCENE.id, [el])
        coro2 = CLIENT.get_els(SCENE.id)
        t1 = group.create_task(coro1)
        t2 = group.create_task(coro2)

    upd_res = t1.result()
    read_res = t2.result()

    assert upd_res.items == []
    assert read_res.items == []

    # later read sync token could be used to get fresh el (other request result)
    read_res = await CLIENT.get_els(SCENE.id, sync_token=read_res.next_sync_token)
    assert read_res.items == [IsPartialSchema(el)]

    # after that no fresh elements to get
    read_res = await CLIENT.get_els(SCENE.id, sync_token=read_res.next_sync_token)
    assert read_res.items == []


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
    results = await CLIENT_A.get_scenes(schemas.SceneFilters(created_by_id="*"))
    assert results.items == [
        IsPartialSchema(created_by_id=USER_A.id),
        IsPartialSchema(created_by_id=USER_A.id),
        IsPartialSchema(created_by_id=USER_B.id),
        IsPartialSchema(created_by_id=USER_B.id),
    ]

    # per project
    results = await CLIENT_A.get_scenes(
        schemas.SceneFilters(created_by_id="*", project_id=PROJECT_B.id),
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
