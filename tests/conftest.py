import logging
import uuid
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from datetime import datetime
from pprint import pformat
from typing import Any, Callable, TypeAlias

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.datastructures import State
from httpx import AsyncClient
from pydantic import SecretStr
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette import status

from app.applications.objective import ObjectiveAPP, ObjectiveRequest
from app.client import ObjectiveClient
from app.config import AppSettings, AsyncDatabaseDriver
from app.dependencies.dependencies import SessionContext
from app.dependencies.users import UserManagerContext
from app.main import setup
from app.repository.models import Base
from app.repository.repositories import DatabaseRepositories
from app.schemas import schemas
from tests.helpers import (
    create_and_drop_tables_by_alembic,
    create_and_drop_tables_by_metadata,
    create_database,
    drop_database,
)

logger = logging.getLogger("conftest")


@pytest.fixture(autouse=True)
def patch_uuid_generator(mocker: MockerFixture):
    counter = 0

    def _side_effect():
        nonlocal counter
        counter += 1
        return uuid.UUID(int=counter)

    mocker.patch.object(uuid, "uuid4", side_effect=_side_effect)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def new_line_session():
    print()
    yield
    print()


@pytest.fixture(autouse=True)
def new_line():
    print()
    yield
    print()


@pytest.fixture(scope="session")
def settings(request: pytest.FixtureRequest) -> AppSettings:
    common: Any = dict(
        # APP_RAISE_SERVER_EXCEPTIONS=[500, 501, 502, 503, 504],
        APP_RAISE_SERVER_EXCEPTIONS=True,
    )

    if request.config.option.postgres:
        settings = AppSettings(
            DATABASE_NAME=f"objective_pytest_{datetime.now()}",
            **common,
        )
        assert settings.DATABASE_URL.drivername == AsyncDatabaseDriver.POSTGRES

    else:
        settings = AppSettings(
            DATABASE_DRIVER=AsyncDatabaseDriver.SQLITE,
            DATABASE_USER=SecretStr(""),
            DATABASE_PASSWORD=SecretStr(""),
            DATABASE_HOST=None,
            DATABASE_PORT=None,
            DATABASE_NAME=":memory:",
            **common,
        )

    return settings


@pytest.fixture
async def app(settings: AppSettings):
    app = setup(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def engine(settings: AppSettings, app: ObjectiveAPP) -> AsyncEngine:
    engine: AsyncEngine = app.state.engine
    return engine


@pytest.fixture
async def setup_database(engine: AsyncEngine):
    if engine.url.drivername == AsyncDatabaseDriver.SQLITE:
        yield
        return

    await create_database(engine.url)
    yield
    await drop_database(engine.url)


@pytest.fixture()
async def setup_tables(
    setup_database: None,
    request: pytest.FixtureRequest,
    engine: AsyncEngine,
    settings: AppSettings,
):
    if request.config.option.alembic:
        async with create_and_drop_tables_by_alembic(engine, settings):
            yield

    else:
        async with create_and_drop_tables_by_metadata(engine, Base.metadata):
            yield


@pytest.fixture
async def session(setup_tables: None, app: ObjectiveAPP):
    async with app.state.session_maker.begin() as session:
        yield session


TDatabaseContext = Callable[[], _AsyncGeneratorContextManager[DatabaseRepositories]]


@pytest.fixture
async def app_request(mocker: MockerFixture, app: ObjectiveAPP):
    request = mocker.Mock()
    request.state = State()
    request.app = app
    return request


TSession: TypeAlias = Callable[[], _AsyncGeneratorContextManager[AsyncSession]]


@pytest.fixture
async def session_context(setup_tables: None, app: ObjectiveAPP) -> TSession:
    @asynccontextmanager
    async def context():
        async with SessionContext(app) as session:
            yield session

    return context


@pytest.fixture
async def database_context(
    app_request: ObjectiveRequest,
    session_context: TSession,
    settings: AppSettings,
    app: ObjectiveAPP,
) -> TDatabaseContext:
    @asynccontextmanager
    async def context():
        async with session_context() as session:
            yield DatabaseRepositories.construct(
                request=app_request,
                session=session,
                settings=settings,
                app=app,
                logger=logger,
            )

    return context


########################################################################################
# Users / Clients
########################################################################################


TEST_USERS = {
    1: schemas.UserCreate(
        email="user_a@test.com",
        password="password",
        username="user_a",
        role="string",
    ),
    2: schemas.UserCreate(
        email="user_b@test.com",
        password="password",
        username="user_b",
        role="string",
    ),
}


@pytest.fixture
async def setup_users(
    app_request: ObjectiveRequest,
    database_context: TDatabaseContext,
    settings: AppSettings,
):
    users: dict[int, schemas.User] = {}
    async with database_context() as db:
        async with UserManagerContext(db, settings) as user_manager:
            for k, user in TEST_USERS.items():
                users[k] = await user_manager.create(user, request=app_request)
    return users


@pytest.fixture
async def setup_tokens(setup_users: dict[int, schemas.User], app: FastAPI):
    tokens = {}
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as session:
        for k, user in TEST_USERS.items():
            response = await session.post(
                "/api/auth/jwt/login",
                data=dict(username=user.email, password="password"),
            )
            assert response.status_code == status.HTTP_200_OK, pformat(response.json())
            tokens[k] = response.json()["access_token"]
    return tokens


@pytest.fixture
async def setup_clients(app: FastAPI, setup_tokens: dict):
    async with AsyncClient(app=app, base_url="http://testserver") as session:
        yield {
            1: ObjectiveClient(
                session,
                headers={"Authorization": f"Bearer {setup_tokens[1]}"},
            ),
            2: ObjectiveClient(
                session,
                headers={"Authorization": f"Bearer {setup_tokens[2]}"},
            ),
            "unauthorized": ObjectiveClient(session),
        }


@pytest.fixture
def client(setup_clients: dict[int, ObjectiveClient]) -> ObjectiveClient:
    return setup_clients[1]


########################################################################################
# data
########################################################################################


@pytest.fixture
def USER_A(setup_users: dict[int, schemas.User]):
    return setup_users[1]


@pytest.fixture
def USER_B(setup_users: dict[int, schemas.User]):
    return setup_users[2]


@pytest.fixture
def CLIENT_A(setup_clients: dict[int, ObjectiveClient]):
    return setup_clients[1]


@pytest.fixture
def CLIENT_B(setup_clients: dict[int, ObjectiveClient]):
    return setup_clients[2]
