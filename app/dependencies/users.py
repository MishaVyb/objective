from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from app.dependencies.dependencies import AppSettingsDepends
from app.repository.models.users import User
from app.repository.repositories import DatabaseRepositoriesDepends
from app.repository.users import UserManager

########################################################################################
# USER
########################################################################################

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
fastapi_users_api = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [fastapi_users_backend],
)
get_active_user = fastapi_users_api.current_user(active=True)

AuthenticatedUser = User  # TODO pydantic schema
AuthenticatedUserDepends = Annotated[AuthenticatedUser, Depends(get_active_user)]
