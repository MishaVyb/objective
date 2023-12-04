import logging
from dataclasses import dataclass, fields
from typing import Annotated, Generic, Literal, Type, TypeVar
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.strategy_options import _AbstractLoad

from objective.db.models.scenes import BaseFieldsMixin
from objective.db.models.users import UserModel
from objective.schemas.base import BaseSchema
from objective.web.dependencies import current_active_user, get_db_session
from objective.web.exceptions import ForbiddenError, NotFoundError

_TModel = TypeVar("_TModel", bound=BaseFieldsMixin)
_SchemaCreate = TypeVar("_SchemaCreate", bound=BaseSchema)
_SchemaUpdate = TypeVar("_SchemaUpdate", bound=BaseSchema)
_TSelect = TypeVar("_TSelect", bound=tuple)

logger = logging.getLogger(__name__)

Action = Literal["create", "read", "update", "delete"]


@dataclass
class FiltersBase:
    is_deleted: bool | None = None

    def emit(self, q: Select[_TSelect]):
        filters = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None:
                filters[field.name] = value

        return q.filter_by(**filters)


class RepositoryBase(Generic[_TModel, _SchemaCreate, _SchemaUpdate]):
    """Base DAO associated with current user."""

    model: Type[_TModel]
    options_one: list[_AbstractLoad] = []
    options_many: list[_AbstractLoad] = []

    def __init__(
        self,
        user: Annotated[UserModel, Depends(current_active_user)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> None:
        self.user = user
        """Current user. """
        self.session = session

    def _has_access_rights(self, obj: _TModel, *, action: Action):
        if action == "read":
            # TMP anyone has read access to anything
            return True

        return obj.user_id == self.user.id

    async def get_one(self, id: UUID, *, action: Action = "read"):
        instance = await self.session.get(
            self.model,
            id,
            options=self.options_one or self.options_many,
        )
        if not instance:
            logger.warning(f"Not Found: {id}")
            raise NotFoundError()
        if not self._has_access_rights(instance, action=action):
            logger.warning(f"Access Denied: {id}")
            raise ForbiddenError()
        return instance

    async def get_many(
        self,
        extra_filters: FiltersBase = None,
        action: Action = "read",
    ):
        """Get many entities. Filtered by current user."""

        q = (
            select(self.model)
            .filter_by(user_id=self.user.id)
            .options(*self.options_many)
        )
        if extra_filters:
            q = extra_filters.emit(q)
        q = q.order_by(self.model.created_at)

        r = await self.session.scalars(q)
        items = r.all()

        for item in items:
            if not self._has_access_rights(item, action=action):
                logger.warning(f"Access Denied: {item.id}")
                raise ForbiddenError()

        return items

    async def create(self, schema: _SchemaCreate, **extra_values):
        project = self.model(**dict(schema), **extra_values, user_id=self.user.id)
        self.session.add(project)
        await self.session.commit()
        return project

    async def update(self, id: UUID, schema: _SchemaUpdate | dict):
        obj = await self.get_one(id, action="update")

        data = dict(updated_by=self.user.id)
        if isinstance(schema, BaseModel):
            data |= schema.model_dump(exclude_unset=True, exclude_defaults=True)
        else:
            data |= schema

        for fieldname, value in data.items():
            setattr(obj, fieldname, value)

        await self.session.commit()
        return obj

    async def delete(self, id: UUID):
        """Mark for delete."""
        # TODO mark delete cascade?
        return await self.update(id, dict(is_deleted=True))
