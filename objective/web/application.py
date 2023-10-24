from contextlib import asynccontextmanager
from importlib import metadata

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import UJSONResponse
from sqlalchemy.ext.asyncio import create_async_engine

from objective.settings import settings
from objective.web.router import api_router


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
        default_response_class=UJSONResponse,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router=api_router, prefix="/api")

    return app
