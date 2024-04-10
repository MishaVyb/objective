import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import UJSONResponse
from sqlalchemy.ext.asyncio import create_async_engine

from objective.common.exceptions import SentryExceptionsHandlers
from objective.settings import settings
from objective.web.router import api_router
from objective.web.sentry import SentryTracingContextDepends

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.db_url, echo=settings.db_echo)
    app.state.db_engine = engine

    yield

    await app.state.db_engine.dispose()


def get_app() -> FastAPI:
    logger.info(f"Initialize app. {settings!r}")

    app = FastAPI(
        title="objective",
        description=settings.environment,
        version=settings.version,
        openapi_url=settings.openapi_url,
        docs_url=settings.docs_url,
        default_response_class=UJSONResponse,
        lifespan=lifespan,
        dependencies=[
            SentryTracingContextDepends(dashboard_url=settings.sentry_url),
        ],
        swagger_ui_parameters={
            "persistAuthorization": True,
            "withCredentials": True,
        },
        redirect_slashes=False,
    )

    origins = ["*"]

    # NOTE: do not use wildcards https://fastapi.tiangolo.com/tutorial/cors/#wildcards
    if settings.environment == "dev":
        origins = ["http://localhost:3000"]
    if settings.environment == "staging":
        origins = ["http://objective.services"]
    if settings.environment == "production":
        origins = ["http://staging.objective.services"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    exc_handlers = SentryExceptionsHandlers(
        debug=True,
        dashboard_url=settings.sentry_dashboard_url,
        #
        # NOTE: workaround to handle CORS issue https://github.com/tiangolo/fastapi/discussions/7319
        headers={
            "Access-Control-Allow-Origin": ", ".join(origins),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )
    exc_handlers.setup(app)

    app.include_router(router=api_router, prefix="/api")

    return app
