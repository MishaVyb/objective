import contextlib

import pytest

from objective.schemas.users import UserCreateSchema
from objective.web.dependencies import get_user_db, get_user_manager

get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


@pytest.fixture
async def user(session):
    async with get_user_db_context(session) as user_db:
        async with get_user_manager_context(user_db) as user_manager:
            user = await user_manager.create(
                UserCreateSchema(
                    email="user@example.com",
                    password="string",
                    username="string",
                    role="string",
                ),
            )
    return user
