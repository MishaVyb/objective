from __future__ import annotations

import logging.config
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Type

import fastapi.datastructures
from fastapi import FastAPI
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

from ..api import projects, scenes, users
from ..config import AppSettings

if TYPE_CHECKING:
    from app.dependencies.users import CurrentUser

logger = logging.getLogger(__name__)


def setup_initial_scenes(app: ObjectiveAPP) -> list[schemas.SceneJsonFilePersistence]:
    scenes = []
    for filepath in app.state.settings.USERS_INITIAL_SCENES:
        with open(filepath) as file:
            scene = schemas.SceneJsonFilePersistence.model_validate_json(file.read())
            scenes.append(scene)
    app.state.initial_scenes = scenes


@asynccontextmanager
async def lifespan(app: ObjectiveAPP):
    setup_initial_scenes(app)

    # try:
    #     # engine could be already present (at pytest session)
    #     engine = app.state.engine
    # except AttributeError:
    engine = app.state.engine = create_async_engine(
        app.state.settings.DATABASE_URL,
        echo=app.state.settings.DATABASE_ECHO,
        echo_pool=app.state.settings.DATABASE_ECHO_POOL,
    )
    app.state.session_maker = async_sessionmaker(
        engine,
        autoflush=True,
        expire_on_commit=True,
    )

    try:
        yield
    finally:
        await engine.dispose()


class ObjectiveAPP(FastAPI):

    if TYPE_CHECKING:

        class State(fastapi.datastructures.State):
            settings: AppSettings
            initial_scenes: list[schemas.SceneJsonFilePersistence]

            current_user: CurrentUser
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
            ValueError

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
            # replace_uvicorn_logging=True, # ???
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
        app.include_router(monitoring.router)
        app.include_router(users.router)
        app.include_router(projects.router)
        app.include_router(scenes.router)

        # setup openapi at the end after app is fully configured
        openapi_schema = app.openapi()
        openapi_schema["openapi"] = "3.0.3"

        return app
