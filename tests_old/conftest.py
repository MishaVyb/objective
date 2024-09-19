import logging
from dataclasses import dataclass
from pprint import pformat

import pytest
from httpx import AsyncClient
from starlette import status

from app.applications.objective import ObjectiveAPP, ObjectiveRequest
from app.config import AppSettings
from app.dependencies.users import UserManagerContext
from app.repository import models
from app.schemas import deprecated_schemas
from common.dataclass.base import DataclassBase
from tests.conftest import *  # TMP

logger = logging.getLogger("conftest")


########################################################################################
# DEPRECATED FIXTURES: Users / Clients
########################################################################################


@dataclass
class UsersFixture(DataclassBase[models.User]):
    user: models.User
    another_user: models.User


@dataclass
class ClientsFixture(DataclassBase[AsyncClient]):
    no_auth: AsyncClient
    user: AsyncClient
    another_user: AsyncClient


@pytest.fixture
async def users(
    app_request: ObjectiveRequest,
    database_context: TDatabaseContext,
    settings: AppSettings,
):

    users = {}
    async with database_context() as db:
        async with UserManagerContext(db, settings) as user_manager:
            for field in UsersFixture.fields():
                users[field.name] = await user_manager.create(
                    deprecated_schemas.UserCreate(
                        email=f"{field.name}@test.com",
                        password="password",
                        username=f"{field.name}",
                        role="string",
                    ),
                    request=app_request,
                )

                await db.all.session.refresh(
                    users[field.name],
                    ["projects", "scenes", "files"],
                )

    return UsersFixture(**users)


@pytest.fixture
async def user(users: UsersFixture):
    """Default user."""
    return users.user


@pytest.fixture
async def clients(app: ObjectiveAPP, users: UsersFixture):
    clients: dict[str, AsyncClient] = {}
    async with AsyncClient(app=app, base_url="http://test") as no_auth_client:
        clients["no_auth"] = no_auth_client

        for fieldname, user in users.asdict().items():
            response = await no_auth_client.post(
                "/api/auth/jwt/login",
                data=dict(username=user.email, password="password"),
            )
            assert response.status_code == status.HTTP_200_OK, pformat(response.json())

            token = response.json()["access_token"]
            clients[fieldname] = await AsyncClient(
                app=app,
                base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ).__aenter__()

        yield ClientsFixture(**clients)

        for fieldname, user in users.asdict().items():
            await clients[fieldname].__aexit__()


@pytest.fixture
async def client(clients: ClientsFixture):
    """Default client."""
    return clients.user
