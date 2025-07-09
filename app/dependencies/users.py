from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Request
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from app.dependencies.dependencies import AppSettingsDepends
from app.repository import models
from app.repository.repositories import DatabaseRepositoriesDepends
from app.repository.users import UserManager

AuthenticatedUser = models.User  # TODO pydantic schema


async def get_user_manager(
    db: DatabaseRepositoriesDepends,
    settings: AppSettingsDepends,
):
    yield UserManager(db, settings)


UserManagerDepends = Annotated[UserManager, Depends(get_user_manager)]
UserManagerContext = asynccontextmanager(get_user_manager)


def get_jwt_strategy(settings: AppSettingsDepends):
    return JWTStrategy(
        secret=settings.USERS_SECRET.get_secret_value(),
        lifetime_seconds=settings.USERS_TOKEN_LIFETIME,
    )


fastapi_users_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="v2/auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)
fastapi_users_api = FastAPIUsers[models.User, uuid.UUID](
    get_user_manager,
    [fastapi_users_backend],
)


# wrap original depends to populate Request state:

_get_auth_user = fastapi_users_api.current_user(active=True)


async def get_auth_user(
    request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(_get_auth_user)],
) -> AuthenticatedUser:
    request.state.current_user = current_user
    return request.state.current_user


AuthRouterDepends = Depends(get_auth_user)
"""Marks route as protected. Authentication is required. """

AuthUserDepends = Annotated[AuthenticatedUser, Depends(get_auth_user)]
"""Resolve current user. """
