import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Literal

import alembic
import pytest
from alembic.config import Config as AlembicConfig
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Request
from httpx import AsyncClient
from pydantic_settings import SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from starlette import status
from tests.utils import async_create_database, async_drop_database

from objective.db.meta import meta
from objective.db.models.users import UserModel
from objective.settings import Settings
from objective.settings import settings as app_settings
from objective.web.application import get_app
from objective.web.dependencies import get_db_session

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


@pytest.fixture(autouse=True)
def new_line():
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


@pytest.fixture
async def not_auth_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def client(not_auth_client: AsyncClient, app: FastAPI, user: UserModel):
    response = await not_auth_client.post(
        "/api/auth/jwt/login",
        data=dict(username="user@example.com", password="string"),
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    token = response.json()["access_token"]
    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


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
