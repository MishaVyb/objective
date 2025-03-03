import logging
import uuid

import pytest
from dirty_equals import AnyThing, IsDatetime, IsList
from fastapi import HTTPException
from starlette import status

from app.applications.objective import ObjectiveAPP
from app.client import ObjectiveClient
from app.exceptions import NotFoundInstanceError
from app.repository.repositories import ProjectRepository
from app.schemas import schemas
from tests.helpers import IsPartialSchema

pytestmark = [
    pytest.mark.anyio,
]


logger = logging.getLogger("conftest")

# TMP
_DEFAULT_PROJECT_NAME = ProjectRepository.DEFAULT_PROJECT_NAME
_DEFAULT_PROJECTS_AMOUNT = 1
_DEFAULT_SCENES_AMOUNT = 2

# DATA
TEST_PROJECT = schemas.ProjectCreate(name="test-project")


async def test_default_project_and_scenes(
    app: ObjectiveAPP,
    client: ObjectiveClient,
    USER: schemas.User,
) -> None:

    # check project
    result = await client.get_projects()
    assert result.items == [
        IsPartialSchema(
            name=_DEFAULT_PROJECT_NAME,
            scenes=IsList(length=_DEFAULT_SCENES_AMOUNT),
            created_by=IsPartialSchema(id=USER.id),
        ),
    ]
    project = result.items[0]

    # check scenes
    result = await client.get_scenes()
    assert result.items == IsList(
        IsPartialSchema(
            name=AnyThing,
            created_by=IsPartialSchema(id=USER.id),
            project=IsPartialSchema(
                id=project.id,
                created_by=IsPartialSchema(id=project.created_by.id),
            ),
        ),
        # ...
        length=_DEFAULT_SCENES_AMOUNT,
    )

    # check files
    file_ids = [file for scene in app.state.initial_scenes for file in scene.files]
    for file_id in file_ids:
        res = await client.get_file(file_id)
        assert res.data


async def test_project_crud(
    client: ObjectiveClient,
    setup_users: dict,
) -> None:
    user_A, user_B = setup_users[1], setup_users[2]

    # [1] create
    result = await client.create_project(TEST_PROJECT)
    assert result == IsPartialSchema(name=TEST_PROJECT.name)

    result = await client.get_project(result.id)
    assert result == IsPartialSchema(name=TEST_PROJECT.name)

    results = await client.get_projects()
    assert results.items == [
        IsPartialSchema(name=_DEFAULT_PROJECT_NAME),  # default
        IsPartialSchema(name=TEST_PROJECT.name),
    ]

    # [2] update
    result = await client.update_project(result.id, schemas.ProjectUpdate(name="upd"))
    assert result == IsPartialSchema(
        created_at=IsDatetime(),
        updated_at=IsDatetime(),
        created_by_id=user_A.id,
        updated_by_id=user_A.id,
        name="upd",
    )

    result = await client.get_project(result.id)
    assert result == IsPartialSchema(name="upd")

    # [3] delete
    result = await client.delete_project(result.id)
    assert result == IsPartialSchema(name="upd", is_deleted=True)

    # [4] recover
    result = await client.update_project(
        result.id,
        schemas.ProjectUpdate(is_deleted=False),
    )
    assert result == IsPartialSchema(name="upd", is_deleted=False)


async def test_project_filters(client: ObjectiveClient) -> None:
    # arrange:
    result = await client.create_project(TEST_PROJECT)
    await client.delete_project(result.id)

    # act:
    results = await client.get_projects()
    assert results.items == [
        IsPartialSchema(name=_DEFAULT_PROJECT_NAME),  # default project
        IsPartialSchema(name=TEST_PROJECT.name),  # deleted project
    ]
    results = await client.get_projects(schemas.ProjectFilters(is_deleted=False))
    assert results.items == [
        IsPartialSchema(name=_DEFAULT_PROJECT_NAME),  # default project
        # IsPartialSchema(name=TEST_PROJECT.name),  # deleted project
    ]
    results = await client.get_projects(schemas.ProjectFilters(is_deleted=True))
    assert results.items == [
        # IsPartialSchema(name=_DEFAULT_PROJECT_NAME),  # default project
        IsPartialSchema(name=TEST_PROJECT.name),  # deleted project
    ]


async def test_project_401(setup_clients: dict[str | int, ObjectiveClient]):
    with pytest.raises(HTTPException) as exc:
        await setup_clients["unauthorized"].get_project(uuid.uuid4())
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


async def test_project_404(client: ObjectiveClient):
    with pytest.raises(NotFoundInstanceError):
        await client.get_project(uuid.uuid4())
