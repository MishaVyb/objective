from __future__ import annotations

import logging.config
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Type

import fastapi.datastructures
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.schemas import schemas
from common.fastapi.exceptions import SentryExceptionsHandlers
from common.fastapi.monitoring.base import JournalRecordMiddleware
from common.fastapi.monitoring.sentry import (
    SentryLoggerMiddleware,
    SentryTracingContextDepends,
)
from common.fastapi.routes import monitoring

from ..api import v1, v2
from ..config import AppSettings

if TYPE_CHECKING:
    from app.dependencies.users import AuthenticatedUser

logger = logging.getLogger(__name__)


def setup_initial_scenes(app: ObjectiveAPP) -> None:
    scenes = []
    for filepath in app.state.settings.USERS_INITIAL_SCENES:
        with open(filepath) as file:
            scene = schemas.SceneJsonFilePersistence.model_validate_json(file.read())
            scenes.append(scene)
    app.state.initial_scenes = scenes


@asynccontextmanager
async def lifespan(app: ObjectiveAPP):
    setup_initial_scenes(app)

    engine = app.state.engine = create_async_engine(
        app.state.settings.DATABASE_URL,
        echo=app.state.settings.DATABASE_ECHO,
        echo_pool=app.state.settings.DATABASE_ECHO_POOL,
    )
    app.state.session_maker = async_sessionmaker(
        engine,
        autoflush=True,
        expire_on_commit=False,  # FIXME db repos should return Pydantic only
    )

    try:
        yield
    finally:
        await engine.dispose()


if TYPE_CHECKING:

    class ObjectiveRequest(Request):
        class State(fastapi.datastructures.State):
            # NOTE
            # populated on 'get_auth_user' depends resolutions
            # and after success User registrations
            current_user: AuthenticatedUser

        state: State

else:
    ObjectiveRequest = Request


class ObjectiveAPP(FastAPI):

    if TYPE_CHECKING:

        class State(fastapi.datastructures.State):
            settings: AppSettings
            initial_scenes: list[schemas.SceneJsonFilePersistence]

            current_user: AuthenticatedUser
            engine: AsyncEngine
            session_maker: async_sessionmaker[AsyncSession]

        state: State

    @classmethod
    def startup(cls: Type[ObjectiveAPP], settings: AppSettings):
        app_depends: list = []

        if settings.SENTRY_DSN:
            app_depends += [
                SentryTracingContextDepends(
                    dashboard_url=str(settings.SENTRY_DASHBOARD_URL),
                ),
            ]

        app = cls(
            title=settings.APP_NAME,
            description=settings.APP_DESCRIPTION,
            version=settings.APP_VERSION,
            openapi_url=str(settings.API_OPENAPI_URL),
            docs_url=str(settings.API_DOCS_URL),
            generate_unique_id_function=lambda route: route.name,
            swagger_ui_parameters=settings.API_SWAGGER_UI_PARAMS,
            # debug=True,
            #
            lifespan=lifespan,
            dependencies=app_depends,
            redirect_slashes=False,
        )
        app.state.settings = settings

        app.add_middleware(JournalRecordMiddleware, access_log=True)
        app.add_middleware(SentryLoggerMiddleware, name=__name__)

        # NOTE:
        # do not use wildcards, because it doesn't allows any authorization
        # https://fastapi.tiangolo.com/tutorial/cors/#wildcards

        # TODO settings .env
        if settings.APP_ENVIRONMENT == "dev":
            origins = [
                "http://localhost:3000",
                "http://192.168.1.124:3000",
            ]

        elif settings.APP_ENVIRONMENT == "staging":
            origins = ["http://staging.objective.services"]

        elif settings.APP_ENVIRONMENT == "production":
            origins = ["http://objective.services"]

        else:
            raise ValueError

        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        exc_handlers = SentryExceptionsHandlers(
            debug=settings.APP_VERBOSE_EXCEPTIONS,
            dashboard_url=str(settings.SENTRY_DASHBOARD_URL),
            custom_encoder={DeclarativeBase: lambda v: str(v)},
            replace_uvicorn_error_log=True,
            raise_server_exceptions=settings.APP_RAISE_SERVER_EXCEPTIONS,
            include_traceback=True,
            traceback_limit=-3,
            #
            # NOTE: workaround to handle CORS issue of error response
            # https://github.com/tiangolo/fastapi/discussions/7319
            headers={
                "Access-Control-Allow-Origin": ", ".join(origins),
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )
        exc_handlers.setup(app)

        # setup routes

        # BACKWARDS CAPABILITY
        _old = APIRouter(prefix=str(settings.API_PREFIX), include_in_schema=False)
        _old.include_router(v2.users.router)
        _old.include_router(v1.routes.projects)
        _old.include_router(v1.routes.scenes)
        _old.include_router(v1.routes.files)

        _v1 = APIRouter(
            prefix=str(settings.API_PREFIX / "v1"),
            generate_unique_id_function=lambda router: f"{router.name}_v1",
            deprecated=True,
        )
        _v1.include_router(v1.routes.projects)
        _v1.include_router(v1.routes.scenes)
        _v1.include_router(v1.routes.files)

        _v2 = APIRouter(
            prefix=str(settings.API_PREFIX / "v2"),
            generate_unique_id_function=lambda router: f"{router.name}_v2",
        )
        _v2.include_router(monitoring.router)
        _v2.include_router(v2.users.router)
        _v2.include_router(v2.routes.projects)
        _v2.include_router(v2.routes.scenes)
        _v2.include_router(v2.routes.files)

        app.include_router(_old)
        app.include_router(_v1)
        app.include_router(_v2)

        # setup openapi at the end after app is fully configured
        openapi_schema = app.openapi()
        openapi_schema["openapi"] = "3.0.3"

        return app
