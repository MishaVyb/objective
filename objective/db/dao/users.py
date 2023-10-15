from __future__ import annotations

import uuid

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import PasswordHelperProtocol

from objective.db.models.users import UserModel
from objective.settings import settings


class UserRepository(SQLAlchemyUserDatabase):
    """Users CRUD."""


class UserManager(UUIDIDMixin, BaseUserManager[UserModel, uuid.UUID]):
    """Manages a user session and its tokens."""

    reset_password_token_secret = settings.users_secret
    verification_token_secret = settings.users_secret

    user_db: SQLAlchemyUserDatabase

    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase,
        password_helper: PasswordHelperProtocol | None = None,
    ):
        super().__init__(user_db, password_helper)

    async def on_after_register(self, user: UserModel, request: Request | None = None):

        from objective.db.dao.projects import ProjectRepository  # FIXME

        self.project_dao = ProjectRepository(user, self.user_db.session)
        return await self.project_dao.create_default()
