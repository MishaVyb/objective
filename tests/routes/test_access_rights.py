import logging
from typing import Any

import pytest

from app.client import ObjectiveClient
from app.schemas import schemas
from common.fastapi.exceptions.exceptions import NotEnoughRights
from tests.conftest import TEST_USERS
from tests.conftest_data import ExcalidrawElement
from tests.helpers import IsPartialSchema

pytestmark = [
    pytest.mark.anyio,
]


logger = logging.getLogger("conftest")


@pytest.fixture
def users() -> dict[int, schemas.UserCreate]:
    return {
        1: TEST_USERS[1].model_remake(is_superuser=False),
        2: TEST_USERS[2].model_remake(is_superuser=False),
    }


async def test_project_access_rights(
    CLIENT_A: ObjectiveClient,
    CLIENT_B: ObjectiveClient,
    USER_A: schemas.User,
    USER_B: schemas.User,
):
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]
    SCENE_B = PROJECT_B.scenes[0]
    upd_project = schemas.ProjectUpdate(name="upd", is_deleted=False)
    upd_scene = schemas.SceneUpdate(name="upd", is_deleted=False)
    create_payload = schemas.SceneCreate(name="name", project_id=PROJECT_B.id)
    copy_payload = schemas.SceneCopy(name="copy", project_id=PROJECT_B.id)
    move_payload = schemas.SceneUpdate(project_id=PROJECT_B.id)

    # [0] default PRIVATE access
    assert PROJECT_B.access == schemas.Access.PRIVATE
    assert SCENE_B.access == schemas.Access.PRIVATE

    # read/update/delete project and project.scene is not allowed
    with pytest.raises(NotEnoughRights):
        result = await CLIENT_A.get_project(PROJECT_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_project(PROJECT_B.id, upd_project)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_project(PROJECT_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.get_scene(SCENE_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(SCENE_B.id, upd_scene)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_scene(SCENE_B.id)

    # read many (other user projects) - empty result
    result_ = await CLIENT_A.get_projects(
        schemas.ProjectFilters(created_by_id=USER_B.id),
    )
    assert result_.items == []

    # read many (all projects) - get only available project
    result_ = await CLIENT_A.get_projects(schemas.ProjectFilters(created_by_id="*"))
    assert result_.items == [
        IsPartialSchema(access=schemas.Access.PRIVATE, created_by_id=USER_A.id),
    ]

    # [1] grant PROTECTED rights
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PROTECTED),
    )
    SCENE_B = PROJECT_B.scenes[0]
    assert PROJECT_B.access == schemas.Access.PROTECTED
    assert SCENE_B.access == schemas.Access.PROTECTED

    # read project and project.scenes is allowed now
    result = await CLIENT_A.get_project(PROJECT_B.id)
    assert result == IsPartialSchema(created_by_id=USER_B.id)
    result = await CLIENT_A.get_scene(SCENE_B.id)
    assert result == IsPartialSchema(created_by_id=USER_B.id)

    # update/delete is not allowed still
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_project(PROJECT_B.id, upd_project)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_project(PROJECT_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(SCENE_B.id, upd_scene)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_scene(SCENE_B.id)

    # create/copy/move scene to project is not allowed still
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.create_scene(create_payload)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.copy_scene(PROJECT_A.scenes[0].id, copy_payload)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(PROJECT_A.scenes[0].id, move_payload)

    # [3] grant PUBLIC rights
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PUBLIC),
    )
    SCENE_B = PROJECT_B.scenes[0]
    assert PROJECT_B.access == schemas.Access.PUBLIC
    assert SCENE_B.access == schemas.Access.PUBLIC

    # read/update/delete is allowed now
    result = await CLIENT_A.get_project(PROJECT_B.id)
    assert result == IsPartialSchema(created_by_id=USER_B.id)
    await CLIENT_A.delete_project(PROJECT_B.id)
    await CLIENT_A.update_project(PROJECT_B.id, upd_project)
    await CLIENT_A.delete_scene(SCENE_B.id)
    await CLIENT_A.update_scene(SCENE_B.id, upd_scene)

    # create to project is allowed now
    scene = await CLIENT_A.create_scene(create_payload)
    assert scene.access == PROJECT_B.access  # new scene takes project access
    assert scene.created_by == PROJECT_B.created_by  # new scene takes project author

    # copy to project is allowed now  # new scene takes project access # new scene takes project author
    scene_to_copy = PROJECT_A.scenes[0]
    copied_scene = await CLIENT_A.copy_scene(scene_to_copy.id, copy_payload)
    assert scene_to_copy.access == schemas.Access.PRIVATE
    assert copied_scene.access == schemas.Access.PUBLIC
    assert scene_to_copy.created_by == PROJECT_A.created_by
    assert copied_scene.created_by == PROJECT_B.created_by

    # move in project is allowed now  # moved scene takes project access # new scene takes project author
    scene_to_move = PROJECT_A.scenes[0]
    assert scene_to_move.access == schemas.Access.PRIVATE
    moved_scene = await CLIENT_A.update_scene(scene_to_move.id, move_payload)
    assert moved_scene.access == schemas.Access.PUBLIC
    assert moved_scene.created_by == PROJECT_B.created_by

    # but changing access is not allowed
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_project(
            PROJECT_B.id,
            schemas.ProjectUpdate(access=schemas.Access.PRIVATE),
        )

    # [4] make project PRIVATE back
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PRIVATE),
    )
    SCENE_B = PROJECT_B.scenes[0]
    assert PROJECT_B.access == schemas.Access.PRIVATE
    assert SCENE_B.access == schemas.Access.PRIVATE


async def test_scene_access_rights(
    *,
    USER_A: schemas.User,
    CLIENT_A: ObjectiveClient,
    USER_B: schemas.User,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]
    SCENE_A = PROJECT_A.scenes[0]
    SCENE_B = PROJECT_B.scenes[0]
    upd_scene = schemas.SceneUpdate(name="upd", is_deleted=False)
    result: Any

    # [0] default PRIVATE access
    assert SCENE_B.access == schemas.Access.PRIVATE

    # read/update/delete scene is not allowed
    with pytest.raises(NotEnoughRights):
        result = await CLIENT_A.get_scene(SCENE_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(SCENE_B.id, upd_scene)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_scene(SCENE_B.id)

    # read many (other user scenes) - empty result
    result = await CLIENT_A.get_scenes(schemas.SceneFilters(created_by_id=USER_B.id))
    assert result.items == []
    result = await CLIENT_A.get_scenes(schemas.SceneFilters(project_id=PROJECT_B.id))
    assert result.items == []

    # read many (all scenes) - get only available scenes
    result = await CLIENT_A.get_scenes(schemas.SceneFilters(created_by_id="*"))
    assert result.items == [
        IsPartialSchema(access=schemas.Access.PRIVATE, created_by_id=USER_A.id),
        IsPartialSchema(access=schemas.Access.PRIVATE, created_by_id=USER_A.id),
    ]

    # [1] grant PROTECTED rights
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(access=schemas.Access.PROTECTED),
    )
    assert SCENE_B.access == schemas.Access.PROTECTED

    # read is allowed now
    # scene.project is included, but not other project.scenes
    result = await CLIENT_A.get_scene(SCENE_B.id)
    assert result.project == IsPartialSchema(SCENE_B.project)
    with pytest.raises(AttributeError):
        result.project.scenes

    # update/delete is not allowed still
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(SCENE_B.id, upd_scene)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.delete_scene(SCENE_B.id)

    # [3] grant PUBLIC rights
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(access=schemas.Access.PUBLIC),
    )
    assert SCENE_B.access == schemas.Access.PUBLIC

    # read/update/delete is allowed now
    result = await CLIENT_A.get_scene(SCENE_B.id)
    await CLIENT_A.delete_scene(SCENE_B.id)
    await CLIENT_A.update_scene(SCENE_B.id, upd_scene)

    # but changing access is not allowed
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.update_scene(
            SCENE_B.id,
            schemas.SceneUpdate(access=schemas.Access.PRIVATE),
        )

    ################################################################################
    # [4] make entire project PUBLIC but then make one scene PRIVATE
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PUBLIC),
    )
    assert PROJECT_B.access == schemas.Access.PUBLIC
    assert PROJECT_B.scenes == [  # both scenes included
        IsPartialSchema(access=schemas.Access.PUBLIC),
        IsPartialSchema(access=schemas.Access.PUBLIC),
    ]
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(access=schemas.Access.PRIVATE),
    )
    assert SCENE_B.access == schemas.Access.PRIVATE

    # check scenes included in project (get many)
    PROJECT_B = (
        await CLIENT_A.get_projects(schemas.ProjectFilters(created_by_id=USER_B.id))
    ).items[0]
    assert PROJECT_B.access == schemas.Access.PUBLIC
    assert PROJECT_B.scenes == [  # both scenes
        # IsPartialSchema(access=schemas.Access.PRIVATE), # !!! not in the result
        IsPartialSchema(access=schemas.Access.PUBLIC),
    ]

    # check scenes included in project (get one)
    PROJECT_B = await CLIENT_A.get_project(PROJECT_B.id)
    assert PROJECT_B.access == schemas.Access.PUBLIC
    assert PROJECT_B.scenes == [  # both scenes
        # IsPartialSchema(access=schemas.Access.PRIVATE), # !!! not in the result
        IsPartialSchema(access=schemas.Access.PUBLIC),
    ]

    # [5] make project PUBLIC back, all scenes became PUBLIC as well
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PUBLIC),
    )
    assert PROJECT_B.scenes == [
        IsPartialSchema(access=schemas.Access.PUBLIC),
        IsPartialSchema(access=schemas.Access.PUBLIC),
    ]

    # [6] On Scene creation scene.access will be taken from project.access
    # [6.1] PUBLIC
    scene = await CLIENT_A.create_scene(
        schemas.SceneCreate(name="new", project_id=PROJECT_B.id),
    )
    assert scene.access == schemas.Access.PUBLIC

    # [6.2] the same for PROTECTED
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PROTECTED),
    )
    scene = await CLIENT_B.create_scene(
        schemas.SceneCreate(name="new", project_id=PROJECT_B.id),
    )
    assert scene.access == schemas.Access.PROTECTED

    # [6.3]  the same for PRIVATE
    PROJECT_B = await CLIENT_B.update_project(
        PROJECT_B.id,
        schemas.ProjectUpdate(access=schemas.Access.PRIVATE),
    )
    scene = await CLIENT_B.create_scene(
        schemas.SceneCreate(name="new", project_id=PROJECT_B.id),
    )
    assert scene.access == schemas.Access.PRIVATE


async def test_scene_elements_access_rights(
    *,
    USER_A: schemas.User,
    CLIENT_A: ObjectiveClient,
    USER_B: schemas.User,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]
    SCENE_A = PROJECT_A.scenes[0]
    SCENE_B = PROJECT_B.scenes[0]
    el = ExcalidrawElement(id="element_1")

    # [0] PRIVATE
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.get_els(SCENE_B.id)
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.reconcile_els(SCENE_B.id, [])  # no elements also no access
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.reconcile_els(SCENE_B.id, [el])

    # [1] PROTECTED
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(access=schemas.Access.PROTECTED),
    )

    await CLIENT_A.get_els(SCENE_B.id)  # ok
    await CLIENT_A.reconcile_els(SCENE_B.id, [])  # no elements - ok
    with pytest.raises(NotEnoughRights):
        await CLIENT_A.reconcile_els(SCENE_B.id, [el])

    # [2] PUBLIC
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(access=schemas.Access.PUBLIC),
    )

    await CLIENT_A.get_els(SCENE_B.id)  # ok
    await CLIENT_A.reconcile_els(SCENE_B.id, [])  # no elements - ok
    await CLIENT_A.reconcile_els(SCENE_B.id, [el])  # also ok


async def test_scene_files_access_rights(
    *,
    USER_A: schemas.User,
    CLIENT_A: ObjectiveClient,
    USER_B: schemas.User,
    CLIENT_B: ObjectiveClient,
) -> None:
    PROJECT_A = (await CLIENT_A.get_projects()).items[0]
    PROJECT_B = (await CLIENT_B.get_projects()).items[0]
    SCENE_A = PROJECT_A.scenes[0]
    SCENE_B = PROJECT_B.scenes[0]

    payload = schemas.FileCreate(
        id="file_1",
        data="data_1",
        type="image/png",
        kind=schemas.FileKind.THUMBNAIL,
    )

    # create and associate file with PRIVATE scene
    assert await CLIENT_B.create_file(payload) == IsPartialSchema(id="file_1")
    assert await CLIENT_B.get_file("file_1") == IsPartialSchema(payload)
    SCENE_B = await CLIENT_B.update_scene(
        SCENE_B.id,
        schemas.SceneUpdate(files=["file_1"]),
    )
    assert SCENE_B.access == schemas.Access.PRIVATE
    assert SCENE_B.files == [
        IsPartialSchema(id="file_1", kind=schemas.FileKind.THUMBNAIL),
    ]

    # file will be available for anybody (no matter scene.access)
    assert await CLIENT_A.get_file("file_1") == IsPartialSchema(payload)
