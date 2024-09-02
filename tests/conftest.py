# from datetime import datetime

# from saber.lib.mock.pytest import skip_package_if_python_version

# skip_package_if_python_version(lt=(3, 11))

# import logging
# import time
# from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
# from dataclasses import dataclass
# from http import HTTPMethod
# from typing import Callable

# import httpx
# import pytest
# import pytest_asyncio
# from asgi_lifespan import LifespanManager
# from fastapi import FastAPI
# from pytest_mock import MockerFixture
# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )

# from saber.lib.endpoints.saber_auth_adapters import GetPermissionResponse
# from saber.lib.mock.aiohttp.mocker import AiohttpMocker, _HTTPMockItem

# from saber.services.time_wheel.app import main
# from saber.services.time_wheel.app.applications.time_wheel import TimeWheelAPP
# from saber.services.time_wheel.app.config import AppSettings, AsyncDatabaseDriver
# from saber.services.time_wheel.app.dependencies.auth import AuthenticatedUser
# from saber.services.time_wheel.app.repository.database import DatabaseRepositories
# from saber.services.time_wheel.app.repository.models import Base
# from saber.services.time_wheel.common.client import (
#     TimeWheelClient,
#     TimeWheelClientDeprecated,
# )
# from saber.services.time_wheel.common.config.config import SaberDocoptOptionsBase
# from saber.services.time_wheel.tests.conftest_data import (
#     TEST_USERS,
#     init_resources,
#     init_users,
#     patch_icaluid_generator,
# )
# from saber.services.time_wheel.tests.conftest_settings import (
#     pytest_addoption,
#     pytest_configure,
#     pytest_runtest_setup,
#     has_marker_e2e,
# )
# from saber.services.time_wheel.tests.helpers import (
#     create_and_drop_tables_by_alembic,
#     create_and_drop_tables_by_metadata,
#     create_database,
#     drop_database,
# )

# logger = logging.getLogger("conftest")


# __all__ = [
#     "pytest_configure",
#     "pytest_addoption",
#     "pytest_runtest_setup",
#     "has_marker_e2e",
#     "init_resources",
#     "init_users",
#     "patch_icaluid_generator",
# ]


# POSTGRES_TEST_DATABASE_PREFIX = "time_wheel_pytest_"


# @pytest.fixture(scope="session", autouse=True)
# def new_line_session():
#     print()
#     yield
#     print()


# @pytest.fixture(autouse=True)
# def new_line():
#     print()
#     yield
#     print()


# @pytest.fixture(autouse=True)
# def mock_datetime_now(mocker: MockerFixture):
#     # freezegun does not provide functionality for patching with side_effect
#     # using this instead
#     # https://docs.python.org/3/library/unittest.mock-examples.html#partial-mocking

#     paths = [
#         "saber.services.time_wheel.maintenance.time_portal.config.datetime",
#     ]

#     def _datetime_now_side_effect(*args, **kwargs):
#         assert False, "Calling 'datetime.now()' is now allowed. "

#     for path in paths:
#         mock = mocker.patch(path)
#         mock.now.side_effect = _datetime_now_side_effect
#         mock.utcnow.side_effect = _datetime_now_side_effect
#         mock.side_effect = lambda *args, **kw: datetime(*args, **kw)


# @pytest.fixture
# def assert_all_responses_were_requested() -> bool:
#     return False


# @pytest.fixture
# def non_mocked_hosts(has_marker_e2e) -> list:
#     return ["testserver", "testserver-google-api"]


# @pytest.fixture(scope="session")
# def settings(request: pytest.FixtureRequest):
#     """
#     Makes test session configurable. Usage:

#     - Run default test session. Using in memory SQLite. No custom settings.

#         `pytest test/ [options]`

#     - Run test session with custom settings file.

#         `pytest test/ [options] --settings ./my_settings.py`

#     - Run test session against `postgres` database. Define connection in settings file.

#         `pytest test/ [options] --settings ./my_settings.py --postgres`

#     - Run test session against `postgres` database and crete tables by `alembic` migrations.

#         `pytest test/ [options] --settings ./my_settings.py --postgres --alembic`
#     """
#     overrides = dict(
#         APP_RAISE_SERVER_EXCEPTIONS=True,
#         ALEMBIC_RUN_MIGRATIONS=False,  # do it by fixtures bellow
#         LOG_HANDLERS=["console"],
#         LOG_DIR_CREATE=False,
#     )
#     if request.config.option.postgres:
#         overrides["DATABASE_DRIVER"] = AsyncDatabaseDriver.POSTGRES
#         overrides["DATABASE_NAME"] = f"{POSTGRES_TEST_DATABASE_PREFIX}{time.time()}"
#     else:
#         overrides["DATABASE_DRIVER"] = AsyncDatabaseDriver.SQLITE
#         overrides["DATABASE_USER"] = ""
#         overrides["DATABASE_PASSWORD"] = ""
#         overrides["DATABASE_HOST"] = None
#         overrides["DATABASE_PORT"] = None
#         overrides["DATABASE_NAME"] = ":memory:"

#     opts = SaberDocoptOptionsBase(
#         debug=True,
#         settings=request.config.option.settings,
#         option=overrides,
#     )
#     settings = main.setup_settings(opts)
#     settings.resolve_secrets()

#     if request.config.option.postgres:
#         if settings.DATABASE_URL.drivername != AsyncDatabaseDriver.POSTGRES:
#             pytest.fail(
#                 f"Invalid database URL for  `--postgres` option: {settings.DATABASE_URL}. "
#                 "Specify connection at `my_settings.py` and provide its path with `--settings` option. "
#             )

#     main.setup_logging(settings)
#     main.setup_database(settings)

#     logger.info("Start pytest session. Settings: %s", settings)
#     return settings


# @pytest_asyncio.fixture
# async def engine(settings: AppSettings):
#     return create_async_engine(
#         settings.DATABASE_URL,
#         echo=settings.DATABASE_ECHO,
#         echo_pool=settings.DATABASE_ECHO_POOL,
#     )


# @pytest_asyncio.fixture
# async def setup_database(engine: AsyncEngine):
#     """Create Postgres test database."""

#     if engine.url.drivername == AsyncDatabaseDriver.SQLITE:
#         yield
#         return

#     await create_database(engine.url)
#     yield
#     await drop_database(engine.url)


# @pytest_asyncio.fixture()
# async def setup_tables(
#     setup_database: None,
#     request: pytest.FixtureRequest,
#     engine: AsyncEngine,
#     settings: AppSettings,
# ):
#     if request.config.option.alembic:
#         async with create_and_drop_tables_by_alembic(engine, settings):
#             yield

#     else:
#         async with create_and_drop_tables_by_metadata(engine, Base.metadata):
#             yield


# @pytest_asyncio.fixture
# async def session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
#     return async_sessionmaker(
#         engine,
#         expire_on_commit=False,
#         autoflush=True,
#     )


# @pytest_asyncio.fixture
# async def session(session_maker: async_sessionmaker[AsyncSession]):
#     async with session_maker.begin() as session:
#         yield session


# @pytest.fixture
# def http(mocker: MockerFixture):
#     with AiohttpMocker(mocker, disable_http=True) as http:
#         yield http


# @dataclass
# class _MockAuth:
#     get_permission: _HTTPMockItem
#     post_permission: _HTTPMockItem
#     """access map"""


# @pytest.fixture
# def auth_user():
#     return AuthenticatedUser(
#         user_id=TEST_USERS[1].id,
#         username=f"TEST_USER_{TEST_USERS[1].id}",
#     )


# @pytest.fixture(autouse=True)
# def mock_auth(
#     http: AiohttpMocker, settings: AppSettings, auth_user: AuthenticatedUser
# ) -> _MockAuth:
#     response = GetPermissionResponse(
#         has_permission=True,
#         user_id=auth_user.id,
#         username=auth_user.username,
#     )
#     return _MockAuth(
#         get_permission=http.patch(
#             HTTPMethod.GET,
#             rf".*/auth/permission/{settings.AUTH_NAMESPACE}/.*",
#             json=response.model_dump(),
#         ),
#         post_permission=http.patch(
#             HTTPMethod.POST,
#             rf".*/auth/permission/{settings.AUTH_NAMESPACE}",
#             json=response.model_dump(),
#         ),
#     )


# @pytest_asyncio.fixture
# async def app(settings: AppSettings, engine: AsyncEngine):
#     app = TimeWheelAPP.startup(settings)
#     app.state.engine = engine  # use the same engine in app, do not create new one
#     async with LifespanManager(app):
#         yield app


# TDatabaseContext = Callable[[], _AsyncGeneratorContextManager[DatabaseRepositories]]


# @pytest_asyncio.fixture
# async def database_context(
#     session_maker: async_sessionmaker[AsyncSession],
#     settings: AppSettings,
#     auth_user: AuthenticatedUser,
# ) -> TDatabaseContext:

#     @asynccontextmanager
#     async def context():
#         async with session_maker.begin() as session:
#             yield DatabaseRepositories.construct(
#                 session,
#                 settings=settings,
#                 logger=logger,
#                 current_user=auth_user,
#             )

#     return context


# @pytest_asyncio.fixture
# async def client(app: FastAPI):
#     async with httpx.AsyncClient(app=app, base_url="http://testserver") as session:
#         yield TimeWheelClient(
#             session,
#             headers={"Authorization": "Bearer TOKEN"},
#             logger=logger,
#         )


# @pytest_asyncio.fixture
# async def client_deprecated(app: FastAPI):
#     async with httpx.AsyncClient(app=app, base_url="http://testserver") as session:
#         yield TimeWheelClientDeprecated(
#             session,
#             headers={"Authorization": "Bearer TOKEN"},
#             logger=logger,
#         )
