import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, TypeAlias

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette import status

from app.applications.objective import ObjectiveAPP
from app.config import AppSettings
from app.dependencies.dependencies import SessionContext
from app.dependencies.users import UserManagerContext
from app.main import setup
from app.repository import models
from app.repository.repositories import DatabaseRepositories
from app.schemas import schemas
from common.dataclass.base import DataclassBase
from tests.helpers import create_and_drop_tables_by_alembic
from tests_old.utils import async_create_database, async_drop_database

logger = logging.getLogger("conftest")


# class AppSettings(Settings):
#     """
#     Extend application settings with any other configuration for tests runnings. Usage::

#         > PYTEST_CREATE_TABLES_BY_METADATA=True pytest -v
#         > PYTEST_DROP_TEST_DATABASES_ON_TEARDOWN=False pytest -v
#     """

#     environment: Literal["pytest"] = "pytest"

#     create_tables_by_metadata: bool = False
#     drop_test_databases_on_teardown: bool = True

#     model_config = SettingsConfigDict(
#         env_file=".env",  # Along side with tool.pytest.ini_options::env
#         env_prefix="PYTEST_",
#         env_file_encoding="utf-8",
#     )


@pytest.fixture(autouse=True, scope="session")
def new_line_session():
    print()
    yield
    print()


@pytest.fixture(autouse=True, scope="function")
def new_line_test():
    print()
    yield
    print()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def settings():
    return AppSettings(DATABASE_NAME=f"objective_pytest_{datetime.now()}")


# @pytest.fixture(scope="session", autouse=True)
# def patch_settings(settings: AppSettings):
#     logger.debug(f"Test session runs with: {settings!r}")

#     with pytest.MonkeyPatch.context() as monkeypatch:
#         for field in settings.model_fields_set:
#             if hasattr(app_settings, field):
#                 monkeypatch.setattr(app_settings, field, getattr(settings, field))
#         yield


@pytest.fixture
async def app(settings: AppSettings):
    app = setup(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def engine(settings: AppSettings, app: ObjectiveAPP):
    engine: AsyncEngine = app.state.engine
    assert "pytest" in (engine.url.database or ""), "Test database required"
    return engine


@pytest.fixture
async def setup_database(settings: AppSettings, engine: AsyncEngine):
    """
    Create test database. Fixture with async implementation of sqlalchemy_utils methods.
    """
    # engine = create_async_engine(settings.DATABASE_URL_STR)  # ???
    await async_create_database(engine.url)

    logger.debug(f"Successfully set up test database: {engine.url}. ")

    yield

    logger.debug("Tear down all test databases. ")
    async with engine.begin() as conn:
        databases = (
            (await conn.execute(text("SELECT datname FROM pg_database")))
            .scalars()
            .all()
        )

    for name in databases:
        if "pytest_" in name:
            await async_drop_database(engine.url.set(database=name))


# @pytest.fixture
# def setup_tables(settings: AppSettings, engine: AsyncEngine, setup_database: None):
#     """
#     Setup tables by running alembic migrations. Docs: https://alembic.sqlalchemy.org/en/latest/api/commands.html

#     If `create_tables_by_metadata`, create tables by actual metadata DDL.
#     It useful for checking latest changes when alembic revision file is not contains that last changes yet.
#     """
#     create_tables_by_metadata = False
#     if create_tables_by_metadata:

#         async def _setup():
#             async with engine.begin() as connection:
#                 await connection.execute(
#                     text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'),
#                 )
#                 await connection.run_sync(Base.metadata.create_all)

#         async def _teardown():
#             async with engine.begin() as connection:
#                 await connection.run_sync(Base.metadata.drop_all)

#         loop = asyncio.get_event_loop()
#         loop.run_until_complete(_setup())
#         yield
#         loop.run_until_complete(_teardown())

#     else:
#         config = AlembicConfig("alembic.ini")
#         alembic.command.upgrade(config, "heads")
#         yield
#         alembic.command.downgrade(config, "base")


@pytest.fixture()
async def setup_tables(
    setup_database: None,
    request: pytest.FixtureRequest,
    engine: AsyncEngine,
    settings: AppSettings,
):

    # if request.config.option.alembic:
    #     async with create_and_drop_tables_by_alembic(engine, settings):
    #         yield

    # else:
    #     async with create_and_drop_tables_by_metadata(engine, Base.metadata):
    #         yield

    async with create_and_drop_tables_by_alembic(engine, settings):
        yield


@pytest.fixture
async def session(setup_tables: None, app: ObjectiveAPP):
    async with SessionContext(app) as session:
        yield session


TSession: TypeAlias = Callable[[], _AsyncGeneratorContextManager[AsyncSession]]


@pytest.fixture
async def session_context(setup_tables: None, app: ObjectiveAPP) -> TSession:
    @asynccontextmanager
    async def context():
        async with SessionContext(app) as session:
            yield session

    return context


TDatabaseContext = Callable[[], _AsyncGeneratorContextManager[DatabaseRepositories]]


@pytest.fixture
async def database_context_no_current_user(
    session_context: TSession,
    settings: AppSettings,
    app: ObjectiveAPP,
) -> TDatabaseContext:
    @asynccontextmanager
    async def context():
        async with session_context() as session:
            yield DatabaseRepositories.construct(
                session,
                settings=settings,
                app=app,
                logger=logger,
                current_user=None,  # set later after user creation
            )

    return context


########################################################################################
#
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
    session: AsyncSession,
    mocker: MockerFixture,
    app: ObjectiveAPP,
    database_context_no_current_user: TDatabaseContext,
    settings: AppSettings,
):
    mock_request = mocker.Mock()
    mock_request.app = app

    users = {}
    async with database_context_no_current_user() as db:
        async with UserManagerContext(db, settings) as user_manager:
            for field in UsersFixture.fields():
                users[field.name] = await user_manager.create(
                    schemas.UserCreate(
                        email=f"{field.name}@test.com",
                        password="password",
                        username=f"{field.name}",
                        role="string",
                    ),
                    request=mock_request,
                )

                await db.users.session.refresh(
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
            assert response.status_code == status.HTTP_200_OK, response.text

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
