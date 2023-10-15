import pytest
from sqlalchemy.exc import InvalidRequestError
from tests.conftest import TSession

from objective.db.dao.projects import ProjectRepository
from objective.db.models.users import UserModel

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.usefixtures("session"),
]


async def test_load_options(user: UserModel, session_context: TSession):
    async with session_context() as session:

        # [1] get many
        dao = ProjectRepository(user, session)
        project = (await dao.get_many())[0]

        assert project.scenes[0].name
        with pytest.raises(InvalidRequestError, match=r"is not available"):
            assert project.scenes[0].elements

        # [2] get one
        dao = ProjectRepository(user, session)
        project = await dao.get_one(user.projects[0].id)

        assert project.scenes[0].name
        with pytest.raises(InvalidRequestError, match=r"is not available"):
            assert project.scenes[0].elements
