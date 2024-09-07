from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
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

if TYPE_CHECKING:
    from app.applications.objective import ObjectiveAPP
else:
    ObjectiveAPP = object

CurrentUser = models.User  # TODO pydantic schema

# UNUSED
# async def get_database_session_no_autocommit(app: AppDepends) -> AsyncGenerator[AsyncSession, None]:
#     async with app.state.session_maker() as session:

#         # NOTE:
#         # no session.begins() with autocommit, because `fastapi_users` implements
#         # `session.commit` explicit call
#         yield session


# async def get_user_repo(db: DatabaseRepositoriesDepends):
#     yield db.users


# UserRepositoryDepends = Annotated[UserRepository, Depends(get_user_repo)]
# UserRepositoryContext = asynccontextmanager(get_user_repo)


async def get_user_manager(
    # user_db: UserRepositoryDepends,
    db: DatabaseRepositoriesDepends,
    settings: AppSettingsDepends,
):
    yield UserManager(db, settings)


UserManagerDepends = Annotated[UserManager, Depends(get_user_manager)]
UserManagerContext = asynccontextmanager(get_user_manager)


def get_jwt_strategy():
    return JWTStrategy(
        secret=settings.users_secret.get_secret_value(),
        lifetime_seconds=3600 * 24 * 7,  # 7 days
    )


fastapi_users_backend = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)
fastapi_users_api = FastAPIUsers[models.User, uuid.UUID](
    get_user_manager,
    [fastapi_users_backend],
)


get_current_active_user = fastapi_users_api.current_user(active=True)


async def get_user(
    app: ObjectiveAPP,
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
) -> CurrentUser:
    app.state.current_user = current_user
    return app.state.current_user


UserDepends = Annotated[CurrentUser, Depends(get_user)]
