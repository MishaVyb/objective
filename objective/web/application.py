from contextlib import asynccontextmanager
from importlib import metadata
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import UJSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import create_async_engine

from objective.settings import settings
from objective.web.lifetime import register_shutdown_event, register_startup_event
from objective.web.routes.router import api_router

APP_ROOT = Path(__file__).parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.db_url, echo=settings.db_echo)
    app.state.db_engine = engine

    yield

    await app.state.db_engine.dispose()


def get_app() -> FastAPI:
    app = FastAPI(
        title="objective",
        version=metadata.version("objective"),
        docs_url=None,  # REMOVE
        redoc_url=None,  # REMOVE
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
        lifespan=lifespan,
    )

    # Adds startup and shutdown events.
    register_startup_event(app)
    register_shutdown_event(app)
    app.include_router(router=api_router, prefix="/api")
    app.mount(  # REMOVE
        "/static",
        StaticFiles(directory=APP_ROOT / "static"),
        name="static",
    )

    return app
