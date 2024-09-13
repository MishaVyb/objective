import logging
import uuid
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Generic,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from fastapi import Depends, Request
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import Select, exc, select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.identity import WeakInstanceDict
from sqlalchemy.orm.interfaces import ORMOption

from app.dependencies.dependencies import AppDepends, AppSettingsDepends, SessionDepends
from app.exceptions import (
    DeletedInstanceError,
    ExpireMissingInstanceError,
    FlushMissingInstanceError,
    MissingAttributesError,
    NotFoundInstanceError,
    RefreshModifiedInstanceError,
)
from app.schemas.base import CreateSchemaMixin, UpdateSchemaMixin
from common.fastapi.monitoring.base import LoggerDepends
from common.schemas.base import BaseSchema, DictModel

from .base import AbstractRepository

if TYPE_CHECKING:
    from app.applications.objective import ObjectiveRequest
    from app.dependencies.users import AuthenticatedUser
    from app.repository.models import DeclarativeFieldsMixin
else:
    DeclarativeFieldsMixin = object
    AuthenticatedUser = object
    ObjectiveRequest = object

logger = logging.getLogger(__name__)

_ModelType = TypeVar("_ModelType", bound=DeclarativeFieldsMixin)
_SchemaType = TypeVar("_SchemaType", bound=BaseModel)
_CreateSchemaType = TypeVar("_CreateSchemaType", bound=CreateSchemaMixin)
_UpdateSchemaType = TypeVar("_UpdateSchemaType", bound=UpdateSchemaMixin)
_IdentityKeyType = tuple[Type[_ModelType], tuple[Any, ...], Optional[Any]]

_CLASS_DEFAULT: Any = object()


class StrongInstanceIdentityMap(Generic[_ModelType]):
    """
    Shared between all repositories during single session mapping.
    Populates local strong references mapping from internal sqlalchemy week references.
    """

    def __init__(self, session: SessionDepends) -> None:
        self._session = session
        self._weak_ref: WeakInstanceDict = self._session.identity_map
        self._strong_ref: dict[_IdentityKeyType[_ModelType], _ModelType] = {}

    def key(self, model: Type[_ModelType], ident: Any) -> _IdentityKeyType[_ModelType]:
        return self._session.identity_key(model, ident)

    def add(self, key: _IdentityKeyType[_ModelType], instance: _ModelType) -> None:
        self._strong_ref[key] = instance

    def has(self, key: _IdentityKeyType[_ModelType]) -> bool:
        return key in self._strong_ref

    def get(self, key: _IdentityKeyType[_ModelType]) -> _ModelType | None:
        return self._strong_ref.get(key)

    def populate(self) -> None:
        self._strong_ref |= {k: v for k, v in self._weak_ref.items()}


class RepositoryLocalStorage(Generic[_ModelType]):
    """
    Model oriented local storage. Expose useful aliases to `StrongInstanceIdentityMap`.
    """

    def __init__(
        self,
        model: Type[_ModelType],
        ref: StrongInstanceIdentityMap,
    ) -> None:
        self._ref = ref
        self._model = model

    def key(self, pk: uuid.UUID) -> _IdentityKeyType[_ModelType]:
        return self._ref.key(self._model, pk)

    def add(self, instance: _ModelType) -> None:
        key = self._ref.key(self._model, instance.id)
        self._ref.add(key, instance)

    def has(self, pk: uuid.UUID) -> bool:
        key = self.key(pk)
        return self._ref.has(key)

    def get(self, pk: uuid.UUID) -> _ModelType | None:
        key = self.key(pk)
        return self._ref.get(key)

    def populate(self) -> None:
        self._ref.populate()


class SQLAlchemyRepository(
    AbstractRepository,
    Generic[_ModelType, _SchemaType, _CreateSchemaType, _UpdateSchemaType],
):

    model: Type[_ModelType]
    schema: Type[_SchemaType]

    class Loading:
        default: Sequence[ORMOption] = ()

    def __init__(
        self,
        request: Request,
        session: SessionDepends,
        storage: Annotated[StrongInstanceIdentityMap, Depends()],
        logger: LoggerDepends,
        app: AppDepends,
        settings: AppSettingsDepends,
    ):
        self.request: ObjectiveRequest = request
        self.session = session
        self.logger = logger
        self.app = app
        self.settings = settings

        self._storage = RepositoryLocalStorage(self.model, storage)

    @property
    def current_user(self) -> AuthenticatedUser:
        return self.request.state.current_user

    async def flush(self, ids: list[uuid.UUID]) -> None:
        # do nothing with StrongInstanceIdentityMap at this point, as sqlalchemy
        # does everything we need with instances that already present at our storage
        if not ids:
            raise ValueError
        instances = []
        for pk in ids:
            inst = self._storage.get(pk)
            if not inst:
                raise FlushMissingInstanceError(self, pk)
            instances.append(inst)
        await self.session.flush(instances)

    def expire(self, ids: list[uuid.UUID]) -> None:
        # does not remove instance from cache, but expire all its attributes
        if not ids:
            raise ValueError
        for pk in ids:
            inst = self._storage.get(pk)
            if not inst:
                raise ExpireMissingInstanceError(self, pk)
            self.session.expire(inst)

    async def exist(self, pk: uuid.UUID) -> bool:
        exists_criteria = select(1).where(self.model.id == pk).exists()
        result = await self.session.execute(select(exists_criteria))
        return bool(result.scalar())

    async def exist_where(self, *clauses, **filters) -> bool:
        exists_criteria = (
            select(self.model).where(*clauses).filter_by(**filters).exists()
        )
        result = await self.session.execute(select(exists_criteria))
        return bool(result.scalar())

    async def get(
        self,
        pk: uuid.UUID,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
    ) -> _SchemaType:
        if refresh:
            instance = await self._get_instance_refresh(pk, options)
        else:
            instance = await self._get_instance(pk, options)
        return self._use_result(instance)

    async def get_one(
        self,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        *clauses,
        **filters,
    ) -> _SchemaType:

        # NOTE
        # because of custom filters it will always trigger database query
        # even if storage has cached that instance already

        self.logger.debug("[DATABASE] Querying %r [%s %s]. ", self, clauses, filters)
        options = self._use_options(options)
        r = await self.session.execute(
            select(self.model).where(*clauses).filter_by(**filters).options(*options),
        )
        try:
            instance = r.scalar_one()
        except exc.NoResultFound:
            raise NotFoundInstanceError(filters)
        if instance.is_deleted:
            raise DeletedInstanceError(str(instance))

        self.logger.debug("[DATABASE] Got: %s", instance)
        self._storage.populate()
        return self._use_result(instance)

    async def get_one_or_none(
        self,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        *clauses,
        **filters,
    ) -> _SchemaType | None:
        try:
            return await self.get_one(options, *clauses, **filters)
        except (DeletedInstanceError, NotFoundInstanceError):
            return None

    async def _get_instance(
        self,
        pk: uuid.UUID,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        *,
        including_deleted: bool = False,
    ) -> _ModelType:
        if inst := self._storage.get(pk):
            self.logger.debug(
                "[DATABASE] Getting %s [id=%s]. Using cached: %s",
                self,
                pk,
                inst,
            )
            return inst

        self.logger.debug(
            "[DATABASE] Getting %s [id=%s]. Not found in cache. Querying database ",
            self,
            pk,
        )
        options = self._use_options(options)
        try:
            instance = await self.session.get_one(self.model, pk, options=options)
        except exc.NoResultFound:
            raise NotFoundInstanceError(str(pk))
        if instance.is_deleted and not including_deleted:
            raise DeletedInstanceError(str(instance))

        self.logger.debug("[DATABASE] Got: %s", instance)
        self._storage.populate()
        return instance

    async def _get_instance_refresh(
        self,
        pk: uuid.UUID,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
    ) -> _ModelType:
        self.logger.debug(
            "[DATABASE] Refreshing %s [id=%s]. Expire and re-fetch. ",
            self,
            pk,
        )

        # NOTE
        # session.refresh(..) won't work here, because of loading option
        # therefore expire and query that instance again

        if inst := self._storage.get(pk):
            if self.session.is_modified(inst):
                raise RefreshModifiedInstanceError(inst, pk)
            self.session.expire(inst)
        else:
            raise ExpireMissingInstanceError(self, pk)

        options = self._use_options(options)
        stm = select(self.model).filter_by(id=pk).options(*options)
        r = await self.session.execute(stm)
        try:
            instance = r.scalar_one()
        except exc.NoResultFound:
            raise NotFoundInstanceError(pk)
        if instance.is_deleted:
            raise DeletedInstanceError(str(instance))
        self._storage.populate()
        return instance

    async def get_all(
        self, *, is_deleted: bool = False, options: Sequence[ORMOption] = _CLASS_DEFAULT
    ) -> list[_SchemaType]:
        return await self.get_where(options=options, is_deleted=is_deleted)

    async def get_where(
        self,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        **filters,
    ) -> list[_SchemaType]:
        stm = self._use_statement_get_instances_list(
            options=options,
            is_deleted=is_deleted,
            **filters,
        )
        items = await self._get_instances_list(stm)
        return self._use_results_list(items)

    async def get_filter(
        self,
        filter_: BaseSchema | None = None,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        **extra_filters,
    ) -> list[_SchemaType]:
        stm = self._use_statement_get_instances_list(
            filter_=filter_,
            options=options,
            is_deleted=is_deleted,
            **extra_filters,
        )
        items = await self._get_instances_list(stm)
        return self._use_results_list(items)

    def _use_statement_get_instances_list(  # separate method for inheritance override
        self,
        filter_: BaseSchema | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        **extra_filters,
    ) -> Select:
        filters = self._use_filter(filter_, **extra_filters)
        options = self._use_options(options)

        self.logger.debug("[DATABASE] Querying %r %s. ", self, filters)
        stm = (
            select(self.model)
            .filter_by(**filters)
            .options(*options)
            .order_by(self.model.created_at)  # VBRN
        )
        return stm

    async def _get_instances_list(self, statement: Select) -> Sequence[_ModelType]:
        r = await self.session.execute(statement)
        items = r.scalars().all()
        self.logger.debug(
            "[DATABASE] Got: %s",
            [str(i) for i in items] if len(items) < 10 else len(items),
        )
        self._storage.populate()
        return items

    async def create(
        self,
        payload: _CreateSchemaType,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        **extra_values,
    ) -> _SchemaType:
        """
        :refresh: Refresh objects after creation.
                  Requires only for relationships eager loading.
        """
        data = self._use_payload_create(payload, **extra_values)
        instance = self.model(**data)
        self.logger.debug("[DATABASE] Add: %s", instance)
        self.session.add(instance)

        # for creation flush always required as uuid.UUID should be populated from db
        self.logger.debug("[DATABASE] Flush: %s", instance)
        await self.session.flush([instance])

        self._storage.add(instance)
        if refresh:
            instance = await self._get_instance_refresh(instance.id, options)
        return self._use_result(instance)

    async def pending_create(
        self,
        payload: _CreateSchemaType,
        **extra_values,
    ) -> None:
        data = self._use_payload_create(payload, **extra_values)
        instance = self.model(**data)
        self.logger.debug("[DATABASE] Add: %s", instance)
        self.session.add(instance)

    async def update(
        self,
        pk: uuid.UUID,
        payload: _UpdateSchemaType | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        # refresh: bool = False # TODO
        **extra_values,
    ) -> _SchemaType:
        data = self._use_payload_update(payload, **extra_values)
        instance = await self._get_instance(
            pk,
            options,
            including_deleted=payload.is_update_recover if payload else False,
        )
        if not data:
            return self._use_result(instance)

        self.logger.debug("[DATABASE] Update: %s. Set values: %s", instance, data)
        for k, v in data.items():
            setattr(instance, k, v)

        if flush:
            self.logger.debug("[DATABASE] Flush: %s", instance)
            await self.session.flush([instance])
        return self._use_result(instance)

    async def pending_update(
        self,
        pk: uuid.UUID,
        payload: _UpdateSchemaType | None = None,
        **extra_values,
    ) -> None:
        """Like `update(..., flush=False)` but without returning."""
        data = self._use_payload_update(payload, **extra_values)
        instance = await self._get_instance(pk)
        if not data:
            return

        self.logger.debug("[DATABASE] Update: %s. Set values: %s", instance, data)
        for k, v in data.items():
            setattr(instance, k, v)

    async def delete(self, pk: uuid.UUID, flush: bool = False) -> None:
        instance = await self._get_instance(pk)

        self.logger.debug("[DATABASE] Delete: %s", instance)
        await self.session.delete(instance)
        if flush:
            await self.session.flush([instance])

    async def delete_by(self, flush: bool = False, **filters) -> None:
        stm = self._use_statement_get_instances_list(options=[], **filters)
        instances = await self._get_instances_list(stm)
        for instance in instances:
            self.logger.debug("[DATABASE] Delete: %s", instance)
            await self.session.delete(instance)
        if flush:
            await self.session.flush(instances)

    def _use_options(self, options: Sequence[ORMOption]) -> Sequence[ORMOption]:
        if options is _CLASS_DEFAULT:
            return self.Loading.default
        return options or ()

    def _use_payload_create(
        self, payload: _CreateSchemaType | _UpdateSchemaType, **extra_values
    ):
        # HACK:
        # sqlalchemy expire all many-to-many / one-to-many relationship on flush
        # if it's not set explicitly on model creation as empty list
        # (obviously, for just created instance, all its list relationships are empty)
        ensure_empty_list_relationships = {
            k: []
            for k, v in inspect(self.model).relationships.items()
            if v.uselist and k not in extra_values
        }
        return self._use_payload(
            payload,
            created_by_id=self.current_user.id,
            **extra_values,
            **ensure_empty_list_relationships,
        )

    def _use_payload_update(
        self, payload: _CreateSchemaType | _UpdateSchemaType | None, **extra_values
    ) -> dict:
        return self._use_payload(
            payload, updated_by_id=self.current_user.id, **extra_values
        )

    def _use_payload(
        self,
        payload: _CreateSchemaType | _UpdateSchemaType | None,
        **extra_values,
    ) -> dict:
        if not payload and not extra_values:
            return {}
        payload = payload or DictModel()

        # NOTE
        # use all model properties except relationships (columns + hybrid_properties)
        # use only fields that were set (useful for partial update methods)
        i = inspect(self.model)
        db_fields = set(i.all_orm_descriptors.keys()) - set(i.relationships.keys())
        payload_fields = payload.model_fields_set & db_fields
        payload_values = payload.model_dump(include=payload_fields)
        return payload_values | extra_values

    def _use_filter(self, filter_: BaseSchema | None, **extra_filters) -> dict:
        if not filter_:
            result_filters = extra_filters
        else:
            result_filters = filter_.model_dump(exclude_unset=True) | extra_filters

        return result_filters

    def _use_result(
        self, instance: _ModelType, *, adapter: TypeAdapter[_SchemaType] | None = None
    ) -> _SchemaType:
        try:
            adapter = adapter or TypeAdapter(self.schema)
            return adapter.validate_python(instance, from_attributes=True)
        except ValidationError as e:
            if "MissingGreenlet" in str(e):
                raise MissingAttributesError(self) from e
            raise e

    def _use_results_list(self, instances: Sequence[_ModelType]) -> list[_SchemaType]:
        adp = TypeAdapter(list[self.schema])  # type: ignore
        return self._use_result(instances, adapter=adp)  # type: ignore

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self})"

    def __str__(self) -> str:
        return repr(self.model.__tablename__)


class CommonSQLAlchemyRepository(SQLAlchemyRepository):
    model = ...

    async def flush(self) -> None:
        """Flush all changes."""
        return await self.session.flush()

    def expire(self):
        """Expire all changes."""
        self.session.expire_all()
