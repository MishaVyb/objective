import uuid
from typing import TYPE_CHECKING, Type

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.password import PasswordHelperProtocol
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.config import AppSettings
from app.dependencies.dependencies import SessionDepends
from app.schemas import schemas

from . import models

if TYPE_CHECKING:
    from app.dependencies.users import AuthenticatedUser
    from app.repository.repositories import DatabaseRepositories
else:
    DatabaseRepositories = object
    AuthenticatedUser = object


class UserRepository(SQLAlchemyUserDatabase[models.User, uuid.UUID]):
    model: Type[models.User] = models.User

    def __init__(self, session: SessionDepends):
        super().__init__(session, self.model)

    @property
    def current_user(self) -> AuthenticatedUser:
        return self.request.state.current_user

    # override to using 'flush' instead of 'commit':

    async def create(self, create_dict: dict) -> models.User:
        user = self.user_table(**create_dict)
        user.id = uuid.uuid4()
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update(self, user: models.User, update_dict: dict) -> models.User:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: models.User) -> None:
        await self.session.delete(user)
        await self.session.flush()


class UserManager(UUIDIDMixin, BaseUserManager[models.User, uuid.UUID]):
    user_db: UserRepository

    def __init__(
        self,
        db: DatabaseRepositories,
        settings: AppSettings,
        password_helper: PasswordHelperProtocol | None = None,
    ):
        self.db = db
        self.reset_password_token_secret = settings.USERS_SECRET
        self.verification_token_secret = settings.USERS_SECRET
        super().__init__(db.users, password_helper)

    async def on_after_register(
        self,
        user: models.User,
        request: Request,
    ) -> schemas.Project:
        # as there are no Request user, populate current user after registration
        request.state.current_user = user
        return await self.db.projects.create_default()
