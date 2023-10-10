from dataclasses import dataclass, fields
from typing import Annotated, Generic, Type, TypeVar
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from objective.db.base import BaseModelFieldsMixin
from objective.db.models.users import UserModel
from objective.schemas.base import BaseSchema
from objective.web.dependencies import current_active_user, get_db_session

_TModel = TypeVar("_TModel", bound=BaseModelFieldsMixin)
_SchemaCreate = TypeVar("_SchemaCreate", bound=BaseSchema)
_SchemaUpdate = TypeVar("_SchemaUpdate", bound=BaseSchema)
_TSelect = TypeVar("_TSelect", bound=tuple)


@dataclass
class FiltersBase:
    is_deleted: bool | None = None
    ...

    def emit(self, q: Select[_TSelect]):
        filters = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None:
                filters[field.name] = value

        return q.filter_by(**filters)


class RepositoryBase(Generic[_TModel, _SchemaCreate, _SchemaUpdate]):
    model: Type[_TModel]

    def __init__(
        self,
        user: Annotated[UserModel, Depends(current_active_user)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> None:
        self.user = user
        self.session = session

    async def get(self, id: UUID):
        return await self.session.get(self.model, id)

    async def get_all(self, filters: FiltersBase):
        q = select(self.model).filter_by(user_id=self.user.id)
        q = filters.emit(q)
        r = await self.session.execute(q)
        return r.scalars().all()

    async def create(self, schema: _SchemaCreate):
        project = self.model(**dict(schema), user_id=self.user.id)
        self.session.add(project)
        await self.session.flush()
        await self.session.commit()
        return project

    async def update(self, id: UUID, schema: _SchemaUpdate | dict):
        q = (
            update(self.model)
            .filter_by(id=id)
            .values(**dict(schema), updated_by=self.user.id)
            .returning(self.model)
        )
        r = await self.session.execute(q)
        await self.session.commit()
        return r.scalars().one()

    async def delete(self, id: UUID):
        """Mark for delete."""
        return await self.update(id, dict(is_deleted=True))
