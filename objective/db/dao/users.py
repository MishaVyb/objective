from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from objective.db.models.users import UserModel
from objective.settings import settings

if TYPE_CHECKING:
    pass


class UserRepository(SQLAlchemyUserDatabase):
    """Users CRUD."""


class UserManager(UUIDIDMixin, BaseUserManager[UserModel, uuid.UUID]):
    """Manages a user session and its tokens."""

    reset_password_token_secret = settings.users_secret
    verification_token_secret = settings.users_secret
