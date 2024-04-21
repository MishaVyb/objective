import asyncio
import contextlib
import logging
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, TypeAlias

import alembic
import pytest
from alembic.config import Config as AlembicConfig
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Request
from httpx import AsyncClient
from pydantic_settings import SettingsConfigDict
from pytest_mock import MockerFixture
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from starlette import status
from tests.utils import async_create_database, async_drop_database

from objective.db.meta import meta
from objective.db.models.users import UserModel
from objective.schemas.users import UserCreateSchema
from objective.settings import Settings
from objective.settings import settings as app_settings
from objective.utils import DataclassBase
from objective.web.application import get_app
from objective.web.dependencies import get_db_session, get_user_db, get_user_manager

get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


logger = logging.getLogger(__name__)


class TestSettings(Settings):
    """
    Extend application settings with any other configuration for tests runnings. Usage::

        > PYTEST_CREATE_TABLES_BY_METADATA=True pytest -v
        > PYTEST_DROP_TEST_DATABASES_ON_TEARDOWN=False pytest -v
    """

    environment: Literal["pytest"] = "pytest"

    create_tables_by_metadata: bool = False
    drop_test_databases_on_teardown: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",  # Along side with tool.pytest.ini_options::env
        env_prefix="PYTEST_",
        env_file_encoding="utf-8",
    )


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
    return TestSettings(db_base=f"pytest_{datetime.now()}")


@pytest.fixture(scope="session", autouse=True)
def patch_settings(settings: TestSettings):
    logger.debug(f"Test session runs with: {settings!r}")

    with pytest.MonkeyPatch.context() as monkeypatch:
        for field in settings.model_fields_set:
            if hasattr(app_settings, field):
                monkeypatch.setattr(app_settings, field, getattr(settings, field))
        yield


@pytest.fixture
async def app():
    app = get_app()
    async with LifespanManager(app):
        yield app


@dataclass
class UsersFixture(DataclassBase[UserModel]):
    user: UserModel
    another_user: UserModel


@dataclass
class ClientsFixture(DataclassBase[AsyncClient]):
    no_auth: AsyncClient
    user: AsyncClient
    another_user: AsyncClient


@pytest.fixture
async def users(session: AsyncSession, mocker: MockerFixture, app: FastAPI):
    mock_request = mocker.Mock()
    mock_request.app = app

    users = {}
    async with get_user_db_context(session) as user_db:
        async with get_user_manager_context(user_db) as user_manager:
            for field in UsersFixture.fields():
                users[field.name] = await user_manager.create(
                    UserCreateSchema(
                        email=f"{field.name}@test.com",
                        password="password",
                        username=f"{field.name}",
                        role="string",
                    ),
                    request=mock_request,
                )

                await user_db.session.refresh(
                    users[field.name],
                    ["projects", "scenes", "files"],
                )

    return UsersFixture(**users)


@pytest.fixture
async def user(users: UsersFixture):
    """Default user."""
    return users.user


@pytest.fixture
async def clients(app: FastAPI, users: UsersFixture):
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


@pytest.fixture
def engine(settings: TestSettings, app: FastAPI):
    engine: AsyncEngine = app.state.db_engine
    assert "pytest" in (engine.url.database or ""), "Test database required"
    return engine


@pytest.fixture(scope="session")
async def setup_database(settings: TestSettings):
    """
    Create test database. Fixture with async implementation of sqlalchemy_utils methods.
    """
    engine = create_async_engine(settings.db_url)
    await async_create_database(engine.url)

    logger.debug(f"Successfully set up test database: {engine.url}. ")

    yield

    if not settings.drop_test_databases_on_teardown:
        return

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


@pytest.fixture
def setup_tables(settings: TestSettings, engine: AsyncEngine, setup_database: None):
    """
    Setup tables by running alembic migrations. Docs: https://alembic.sqlalchemy.org/en/latest/api/commands.html

    If `create_tables_by_metadata`, create tables by actual metadata DDL.
    It useful for checking latest changes when alembic revision file is not contains that last changes yet.
    """
    if settings.create_tables_by_metadata:

        async def _setup():
            async with engine.begin() as connection:
                await connection.execute(
                    text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'),
                )
                await connection.run_sync(meta.create_all)

        async def _teardown():
            async with engine.begin() as connection:
                await connection.run_sync(meta.drop_all)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(_setup())
        yield
        loop.run_until_complete(_teardown())

    else:
        config = AlembicConfig("alembic.ini")
        alembic.command.upgrade(config, "heads")
        yield
        alembic.command.downgrade(config, "base")


@pytest.fixture
async def session(setup_tables: None, app: FastAPI):
    scope = dict(type="http", app=app)
    request = Request(scope)

    context = asynccontextmanager(get_db_session)
    async with context(request) as session:
        yield session


TSession: TypeAlias = Callable[[], _AsyncGeneratorContextManager[AsyncSession]]


@pytest.fixture
async def session_context(setup_tables: None, app: FastAPI) -> TSession:
    scope = dict(type="http", app=app)
    request = Request(scope)
    request_session_context = asynccontextmanager(get_db_session)

    @asynccontextmanager
    async def _test_session_context():
        async with request_session_context(request) as session:
            yield session

    return _test_session_context
