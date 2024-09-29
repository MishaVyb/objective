import time
import uuid
from dataclasses import dataclass, fields
from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any, Never, Self, Sequence
from uuid import UUID

from fastapi import Depends
from sqlalchemy import ColumnExpressionArgument, Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import ORMOption
from typing_extensions import deprecated

from app.config import AppSettings
from app.repository.users import UserRepository
from app.schemas.schemas import FiltersBase
from common.fastapi.exceptions.exceptions import NotEnoughRights
from common.repo.sqlalchemy import (
    _CLASS_DEFAULT,
    CommonSQLAlchemyRepository,
    SQLAlchemyRepository,
    StrongInstanceIdentityMap,
    _CreateSchemaType,
    _ModelType,
    _SchemaType,
    _UpdateSchemaType,
)

from . import models, schemas

if TYPE_CHECKING:
    from app.applications.objective import ObjectiveAPP, ObjectiveRequest
else:
    ObjectiveAPP = object
    ObjectiveRequest = object

_CURRENT_USER: Any = object()


# NOTE: Specific logic for Objective only (not common)
class ServiceRepositoryBase(
    SQLAlchemyRepository[_ModelType, _SchemaType, _CreateSchemaType, _UpdateSchemaType],
):
    db: "DatabaseRepositories"

    def _use_filters(
        self,
        filters: schemas.FiltersBase | None,
        *,
        is_deleted: bool = False,
        **extra_filters,
    ) -> dict:
        if is_deleted:
            raise NotImplementedError  # using is_deleted flag from request Query

        if filters:

            # default filters:
            if "created_by_id" not in filters.model_fields_set:
                filters.created_by_id = self.current_user.id

            # filters modifications:
            if filters.created_by_id == "current_user":
                filters.created_by_id = self.current_user.id
            if filters.created_by_id == "":
                filters = filters.model_remake(_self_exclude={"created_by_id"})

        return super()._use_filters(filters, **extra_filters)

    async def create(
        self,
        payload: _CreateSchemaType,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        **extra_values,
    ) -> _SchemaType:
        instance = await super().create(payload, options, refresh, **extra_values)
        await self.check_create_rights(instance)
        return instance

    async def update(
        self,
        pk: UUID,
        payload: _UpdateSchemaType | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        refresh: bool = False,
        **extra_values,
    ) -> _SchemaType:
        instance = await super().update(
            pk, payload, options, flush, refresh, **extra_values
        )
        await self.check_update_rights(instance)
        return instance

    # TODO check access rights
    # async def pending_create(self, payload: _CreateSchemaType, **extra_values) -> None:
    #     instance = await super().pending_create(payload, **extra_values)
    #     await self.check_create_rights(instance)
    #     return instance

    # async def pending_update(
    #     self, pk: UUID, payload: _UpdateSchemaType | None = None, **extra_values
    # ) -> None:
    #     instance = await super().pending_update(pk, payload, **extra_values)
    #     await self.check_create_rights(instance)
    #     return instance

    # TMP solution
    async def check_read_rights(self, instance: _SchemaType):
        pass

    async def check_create_rights(self, instance: _SchemaType):
        pass

    async def check_update_rights(self, instance: _SchemaType):
        if self.current_user.id != instance.created_by_id:  # type: ignore
            raise NotEnoughRights(f"Not enough rights to update: {instance}")


class ProjectRepository(
    ServiceRepositoryBase[
        models.Project,
        schemas.Project,
        schemas.ProjectCreate,
        schemas.ProjectUpdate,
    ],
):
    model = models.Project
    schema = schemas.Project

    class Loading(ServiceRepositoryBase.Loading):
        default = [
            selectinload(models.Project.scenes),
        ]

    # DEPRECATED
    DEFAULT_PROJECT_NAME = "Examples"
    DEFAULT_SCENE_NAME = "Untitled Scene"

    @deprecated("")
    async def create_default(self) -> schemas.Project:
        initial = self.app.state.initial_scenes
        return await self.create(
            schemas.ProjectCreate(name=self.DEFAULT_PROJECT_NAME),
            scenes=[scene for scene in initial],
            files=[
                schemas.FileCreate.model_build(file)
                for scene in initial
                for file in scene.files.values()
            ],
        )

    async def create(
        self,
        payload: schemas.ProjectCreate,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        *,
        scenes: list[schemas.SceneCreate | schemas.SceneJsonFilePersistence] = [],
        files: list[schemas.FileCreate | schemas.FileJsonPersistence] = [],
        **extra_values,
    ) -> schemas.Project:
        project = await super().create(payload, options, refresh, **extra_values)

        for scene in scenes:
            await self.db.scenes.create(
                schemas.SceneCreate.model_build(
                    scene,
                    name=scene.name,
                    project_id=project.id,
                    files=files,
                ),
            )

        return project


class SceneRepository(
    ServiceRepositoryBase[
        models.Scene,
        schemas.SceneExtendedInternal,
        schemas.SceneCreate,
        schemas.SceneUpdate,
    ],
):
    model = models.Scene
    schema = schemas.SceneExtendedInternal

    class Loading(ServiceRepositoryBase.Loading):
        default = [
            joinedload(models.Scene.project),
            selectinload(models.Scene.elements),
        ]

    async def create(
        self,
        payload: schemas.SceneCreate,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        **extra_values,
    ) -> schemas.SceneExtendedInternal:
        scene = await super().create(
            payload,
            options,
            refresh,
            **extra_values,
        )
        for file in payload.files:
            if not await self.db.files.exist_where(id=file.id):
                await self.db.files.create(file)

        for el in payload.elements or []:
            await self.db.elements.pending_create(el, _scene_id=scene.id)

        await self.db.all.flush()
        return await self.get(scene.id, refresh=True)

    # TMP easy solution
    async def check_create_rights(self, instance: schemas.SceneExtended):
        if self.current_user.id != instance.project.created_by_id:
            raise NotEnoughRights(f"Not enough rights to update: {instance.project}")


class ElementRepository(
    ServiceRepositoryBase[  # type: ignore
        models.Element,
        schemas.ElementInternal,  # get
        schemas.Element,  # create
        schemas.Element,  # update
    ],
):
    model = models.Element
    schema = schemas.ElementInternal

    def _use_payload(self, payload: schemas.Element | None, **extra_values) -> dict:
        extra_values.pop("created_by_id", None)
        extra_values.pop("updated_by_id", None)
        data = super()._use_payload(payload, **extra_values)
        if payload:
            data["_json"] = payload.model_dump(exclude_unset=True)
        return data

    # NOTE  no ORDER BY statement for Elements
    def _use_statement_get_instances_list(
        self,
        filters: FiltersBase | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        clauses: list[ColumnExpressionArgument] = (),
        **extra_filters,
    ) -> Select:
        filters = self._use_filters(filters, is_deleted=is_deleted, **extra_filters)
        options = self._use_options(options)

        self.logger.debug("[DATABASE] Querying %r %s. ", self, filters)
        stm = select(self.model).where(*clauses).filter_by(**filters).options(*options)
        return stm

    async def sync(
        self,
        scene_id: uuid.UUID,
        payload: schemas.SyncElementsRequest,
        filters: schemas.ElementsFilters,
    ):
        payload_els = {el.id: el for el in payload.items}

        # ???
        # - using client 'updated' timestamp, not 'created_at'
        # - respond with all updated items from prev sync,
        #   including those that uses just sent himself
        items = await self.db.elements.get_where(
            clauses=[
                self.model._scene_id == scene_id,
                or_(
                    # using payload element ids and updated timestamp to get
                    # - elements to merge
                    # - elements to respond
                    self.model.id.in_(payload_els),
                    self.model._updated > filters.sync_token,
                ),
            ],
        )
        db_els = {el.id: el for el in items}
        new_els = {el.id: el for el in payload_els.values() if el.id not in db_els}
        merge_els = {el.id: el for el in payload_els.values() if el.id in db_els}

        # new db elements to respond with
        respond_els = {el.id: el for el in db_els.values() if el.id not in payload_els}

        # reconcile existing
        for element_id in merge_els:
            payload_el = payload_els[element_id]
            current_el = db_els[element_id]

            # UNUSED
            # It's looks like 'version' is unused placeholder because we have
            # to compare which version is more actual depending on 'updated'
            # timestamp (not el version), because different updates might came
            # with equal version..
            #
            # if payload_el.version > current_el.version:

            if payload_el.version_nonce == current_el.version_nonce:
                # the same client request sync for the same element twice (or more)
                # assuming elements are fully equal
                continue

            # 2 clients have made update for the same element
            # - one client update has been stored already
            # - another client change just has come

            # figure out who made last update on client side
            if payload_el.updated < current_el.updated:
                # extend respond items with element to update on client side
                respond_els[element_id] = current_el
                continue

            await self.pending_update((scene_id, element_id), payload_el)

        # append new
        for el in new_els.values():
            await self.pending_create(el, _scene_id=scene_id)

        await self.session.flush()
        next_sync_token = time.time()
        return schemas.SyncElementsResponse.model_construct(
            items=list(respond_els.values()),
            next_sync_token=next_sync_token,
        )

    # FIXME typing
    async def pending_update(
        self, pk: Any, payload: schemas.Element | None = None, **extra_values
    ) -> None:
        return await super().pending_update(pk, payload, **extra_values)


class FileRepository(
    ServiceRepositoryBase[
        models.File,
        schemas.FileExtended,
        schemas.FileCreate,
        Never,
    ],
):
    model = models.File
    schema = schemas.FileExtended


@dataclass(kw_only=True)
class DatabaseRepositories:
    all: Annotated[CommonSQLAlchemyRepository, Depends()]

    projects: Annotated[ProjectRepository, Depends()]
    scenes: Annotated[SceneRepository, Depends()]
    elements: Annotated[ElementRepository, Depends()]
    files: Annotated[FileRepository, Depends()]

    users: Annotated[UserRepository, Depends()]

    def __post_init__(self) -> None:
        for repo in self.repositories:
            repo.db = self

    @classmethod
    def construct(
        cls,
        request: ObjectiveRequest,
        session: AsyncSession,
        app: ObjectiveAPP,
        settings: AppSettings,
        logger: Logger,
    ) -> Self:
        # storage shared between all repositories for single session
        storage = StrongInstanceIdentityMap(session)
        return cls(
            # SQLAlchemyRepositories:
            **{
                field.name: field.type(
                    request=request,
                    session=session,
                    storage=storage,
                    logger=logger,
                    app=app,
                    settings=settings,
                )
                for field in fields(cls)
                if field.name != "users"
            },
            # other:
            users=UserRepository(session=session),
        )

    @property
    def repositories(self) -> list[ServiceRepositoryBase]:
        return [getattr(self, field.name) for field in fields(self)]


DatabaseRepositoriesDepends = Annotated[DatabaseRepositories, Depends()]
