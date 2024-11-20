import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, AsyncGenerator

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from common.fastapi.monitoring.base import LoggerDepends

if TYPE_CHECKING:
    from app.applications.objective import ObjectiveAPP
    from app.config import AppSettings
    from app.dependencies.users import AuthenticatedUser
else:
    ObjectiveAPP = object
    AppSettings = object
    AuthenticatedUser = object

logger = logging.getLogger(__name__)


def get_app(request: Request) -> ObjectiveAPP:
    return request.app


AppDepends = Annotated[ObjectiveAPP, Depends(get_app)]


def get_app_settings(app: AppDepends) -> AppSettings:
    return app.state.settings


AppSettingsDepends = Annotated[AppSettings, Depends(get_app_settings)]


async def get_httpx_session(settings: AppSettingsDepends):
    async with httpx.AsyncClient(timeout=settings.HTTP_SESSION_TIMEOUT) as client:
        yield client


HTTPXSessionDepends = Annotated[httpx.AsyncClient, Depends(get_httpx_session)]
"""Common HTTPX client session dependency. """

HTTPXSessionContext = asynccontextmanager(get_httpx_session)
"""Common HTTPX client session context. """


async def get_database_session(app: AppDepends) -> AsyncGenerator[AsyncSession, None]:
    """Begin database transaction with autocommit / rollback."""
    async with app.state.session_maker.begin() as session:
        yield session


SessionDepends = Annotated[AsyncSession, Depends(get_database_session)]
"""Common database session dependency. """

SessionContext = asynccontextmanager(get_database_session)
"""Common database session context. """


# UNUSED
# NOTE: get user from Request populated by another dependency before

# class NoAuthenticatedUserStab:
#     pass

# async def get_request_user(request: Request) -> AuthenticatedUser:
#     try:
#         return request.state.authenticated_user
#     except AttributeError:
#         return NoAuthenticatedUserStab()  # type: ignore

# RequestUserDepends = Annotated[AuthenticatedUser, Depends(get_request_user)]


async def debug_freeze_depends(
    logger: LoggerDepends,
    settings: AppSettingsDepends,
) -> None:
    logger.warning("Debug freeze for %s sec. ", settings.APP_DEBUG_FREEZE)
    await asyncio.sleep(settings.APP_DEBUG_FREEZE or 0)
