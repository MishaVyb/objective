import uuid
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette.requests import Request

from objective.db.dao.users import UserManager, UserRepository
from objective.db.models.users import UserModel
from objective.settings import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    Session


async def get_db_session(request: Request):
    engine: AsyncEngine = request.app.state.db_engine
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_db_session)):
    yield UserRepository(session, UserModel)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


def get_jwt_strategy():
    return JWTStrategy(
        secret=settings.users_secret.get_secret_value(),
        lifetime_seconds=3600 * 24 * 7,  # 7 days
    )


auth_jwt = AuthenticationBackend(
    name="jwt",
    transport=BearerTransport(tokenUrl="auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)
api_users = FastAPIUsers[UserModel, uuid.UUID](get_user_manager, [auth_jwt])

# user dependency, that base on `get_user_manager` dep:
current_active_user = api_users.current_user(active=True)
