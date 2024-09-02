import uuid
from typing import TYPE_CHECKING, Type

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.password import PasswordHelperProtocol
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.config import AppSettings
from app.dependencies.dependencies import SessionDepends

from . import models

if TYPE_CHECKING:
    from app.repository.repositories import DatabaseRepositories
else:
    DatabaseRepositories = object

# NOTE
# another module to resolve circular imports from 'repositories.py'


class UserRepository(SQLAlchemyUserDatabase):
    model: Type[models.User] = models.User

    def __init__(
        self,
        session: SessionDepends,
        **_,  # capability with SQLAlchemyRepository
    ):
        super().__init__(session, self.model)


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
        request: Request | None = None,
    ):
        return await self.db.projects.create_default(request)
