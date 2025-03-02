import asyncio
import time
import uuid
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any, Never, Self, Sequence, TypeVar, cast
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
from common.fastapi.exceptions.exceptions import NotEnoughRights, NotFoundError
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


class ServiceRepositoryBase(
    SQLAlchemyRepository[_ModelType, _SchemaType, _CreateSchemaType, _UpdateSchemaType],
):
    """
    Specific logic for Objective services only (not common).
    """

    db: "DatabaseRepositories"  # initialized in DatabaseRepositories.__post_init__

    def _use_filters(
        self,
        filters: schemas.FiltersBase | None,
        *,
        is_deleted: bool = False,  # is deleted flag is omitted
        **extra_filters,
    ) -> dict:
        if is_deleted:
            raise NotImplementedError
        return super()._use_filters(filters, **extra_filters)


_EntitySchemaType = TypeVar(
    "_EntitySchemaType",
    bound=schemas.Project | schemas.SceneSimplified,
)
_CreateEntitySchemaType = TypeVar(
    "_CreateEntitySchemaType",
    bound=schemas.ProjectCreate | schemas.SceneCreate,
)
_UpdateEntitySchemaType = TypeVar(
    "_UpdateEntitySchemaType",
    bound=schemas.ProjectUpdate | schemas.SceneUpdate,
)


class ProjectsScenesServicesRepositoryBase(
    ServiceRepositoryBase[
        _ModelType,
        _EntitySchemaType,
        _CreateEntitySchemaType,
        _UpdateEntitySchemaType,
    ],
):
    """
    Base logic for Objective ententes (Projects and Scenes).

    - Applies common filters
    - Applies access rights for read, create, update actions.
    """

    def _use_filters(
        self,
        filters: schemas.FiltersBase | None,
        *,
        is_deleted: bool = False,
        **extra_filters,
    ) -> dict:
        if filters:

            # filters modifications:
            if filters.created_by_id == schemas.FiltersBase.CreatedBy.current_user:
                filters.created_by_id = self.current_user.id
            if filters.created_by_id == schemas.FiltersBase.CreatedBy.any:
                filters = filters.model_remake(_self_exclude={"created_by_id"})

        return super()._use_filters(filters, is_deleted=is_deleted, **extra_filters)

    async def get(
        self,
        pk: uuid.UUID,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
    ) -> _EntitySchemaType:
        r = await super().get(pk, options=options, refresh=refresh)
        if not await self.check_read_rights(r):
            raise NotEnoughRights(f"Not enough rights to read: {r}")
        return r

    async def get_filter(
        self,
        filters: schemas.FiltersBase | None = None,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        clauses: list[ColumnExpressionArgument] = (),
        **extra_filters,
    ) -> list[_EntitySchemaType]:
        r = await super().get_filter(
            filters,
            options=options,
            is_deleted=is_deleted,
            clauses=clauses,
            **extra_filters,
        )
        return await self.use_items_list(r)

    async def create(
        self,
        payload: _CreateEntitySchemaType,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        **extra_values,
    ) -> _EntitySchemaType:
        instance = await super().create(payload, options, refresh, **extra_values)
        if not await self.check_create_rights(instance):
            raise NotEnoughRights(f"Not enough rights to create: {instance}")
        return instance

    async def update(
        self,
        pk: UUID,
        payload: _UpdateEntitySchemaType | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        refresh: bool = False,
        **extra_values,
    ) -> _EntitySchemaType:
        instance = await super().update(
            pk, payload, options, flush, refresh, **extra_values
        )
        if not await self.check_update_rights(instance, payload):
            raise NotEnoughRights(f"Not enough rights to update: {instance}")
        return instance

    async def pending_create(
        self, payload: _CreateEntitySchemaType, **extra_values
    ) -> None:
        # WARNING: no rights verification, should be used in authorized context only
        return await super().pending_create(payload, **extra_values)

    async def pending_update(
        self, pk: UUID, payload: _UpdateEntitySchemaType | None = None, **extra_values
    ) -> None:
        # WARNING: no rights verification, should be used in authorized context only
        return await super().pending_update(pk, payload, **extra_values)

    # access rights:

    def is_author_or_admin(self, instance: schemas.EntityMixin) -> bool:
        return (
            self.current_user.id == instance.created_by_id
            or self.current_user.is_superuser
        )

    async def check_create_rights(self, instance: _EntitySchemaType) -> bool:
        raise NotImplementedError

    async def check_read_rights(self, instance: _EntitySchemaType) -> bool:
        if instance.access == schemas.Access.PRIVATE:
            return self.is_author_or_admin(instance)

        elif instance.access == schemas.Access.PROTECTED:
            return True

        elif instance.access == schemas.Access.PUBLIC:
            return True

    async def check_update_rights(
        self,
        instance: _EntitySchemaType,
        payload: _UpdateEntitySchemaType | None,
    ) -> bool:
        is_author = self.is_author_or_admin(instance)

        # only author cas set entity Access
        if payload and payload.access and is_author is False:
            return False

        if instance.access == schemas.Access.PRIVATE:
            return is_author

        elif instance.access == schemas.Access.PROTECTED:
            return is_author

        elif instance.access == schemas.Access.PUBLIC:
            return True

    async def use_items_list(
        self,
        r: list[_EntitySchemaType],
    ) -> list[_EntitySchemaType]:
        result = []
        for item in r:
            if await self.check_read_rights(item):
                result.append(item)
            else:
                self.logger.warning("Not enough rights to read: %r. Skip. ", item)
        return result


class ProjectRepository(
    ProjectsScenesServicesRepositoryBase[
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
            joinedload(models.Project.created_by),
            selectinload(models.Project.scenes).joinedload(models.Scene.created_by),
            selectinload(models.Project.scenes)
            .selectinload(models.Scene.files)
            .load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
        ]

    async def get(
        self,
        pk: uuid.UUID,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
    ) -> schemas.Project:
        r = await super().get(pk, options=options, refresh=refresh)
        await self.use_project_scenes([r])
        return r

    async def get_filter(
        self,
        filters: schemas.FiltersBase | None = None,
        *,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        is_deleted: bool = False,
        clauses: list[ColumnExpressionArgument] = (),
        **extra_filters,
    ) -> list[schemas.Project]:
        result = await super().get_filter(
            filters,
            options=options,
            is_deleted=is_deleted,
            clauses=clauses,
            **extra_filters,
        )
        await self.use_project_scenes(result)
        return result

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

    async def update(
        self,
        pk: UUID,
        payload: schemas.ProjectUpdate | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        refresh: bool = False,
        **extra_values,
    ) -> schemas.Project:
        res = await super().update(pk, payload, options, flush, refresh, **extra_values)

        # set the same Access for all project scenes
        if payload and payload.access:
            for scene in res.scenes:
                await self.db.scenes_simplified.pending_update(
                    scene.id,
                    schemas.SceneUpdate(access=payload.access),
                )
            res = await self.get(res.id, refresh=True)

        return res

    async def check_create_rights(self, instance: schemas.Project) -> bool:
        return True

    async def use_project_scenes(self, projects: list[schemas.Project]):
        for project in projects:
            project.scenes = await self.db.scenes.use_items_list(
                cast(list[schemas.SceneExtendedInternal], project.scenes),
            )


class SceneRepository(
    ProjectsScenesServicesRepositoryBase[
        models.Scene,
        schemas.SceneExtendedInternal,
        schemas.SceneCreate,
        Never,
    ],
):
    model = models.Scene
    schema = schemas.SceneExtendedInternal

    class Loading(ServiceRepositoryBase.Loading):
        default = [
            joinedload(models.Scene.created_by),
            joinedload(models.Scene.project).joinedload(models.Project.created_by),
            selectinload(models.Scene.elements),
            selectinload(models.Scene.files).load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
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

    async def update(self, *args, **kwargs):
        raise NotImplementedError(f"{SceneSimplifiedRepository} should be used. ")

    async def pending_update(self, *args, **kwargs):
        raise NotImplementedError(f"{SceneSimplifiedRepository} should be used. ")

    async def check_create_rights(self, instance: schemas.SceneExtended) -> bool:
        """Check is scene can be created in desired project."""
        return await self.db.projects.check_update_rights(
            instance.project,
            payload=None,
        )


class SceneSimplifiedRepository(
    ProjectsScenesServicesRepositoryBase[
        models.Scene,
        schemas.SceneWithProject,
        Never,
        schemas.SceneUpdate,
    ],
):
    """Scene repository without loading Elements. Is's used for UPDATE action."""

    model = models.Scene
    schema = schemas.SceneWithProject

    class Loading(ServiceRepositoryBase.Loading):
        default = [
            # no elements loading
            joinedload(models.Scene.created_by),
            joinedload(models.Scene.project).joinedload(models.Project.created_by),
            selectinload(models.Scene.files).load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
        ]

    async def update(
        self,
        pk: UUID,
        payload: schemas.SceneUpdate | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        refresh: bool = False,
        **extra_values,
    ) -> schemas.SceneWithProject:
        instance = await super().update(
            pk, payload, options, flush, refresh, **extra_values
        )

        # handle relationship
        if payload and payload.files is not None:

            # delete many-to-many association
            await self.db.files_to_scenes.delete_by(scene_id=instance.id)

            # delete render file itself
            for render in instance.files:
                if render.id not in payload.files:
                    await self.db.files.delete(render.id)  # type: ignore

            # creating new
            for file_id in payload.files:
                if not await self.db.files.exist_where(id=file_id):
                    raise NotFoundError(f"File does not exist: {file_id}")
                await self.db.files_to_scenes.pending_create(
                    schemas.FileToSceneInternal(file_id=file_id, scene_id=instance.id),
                )

        await self.flush([pk])
        return await self.get(pk, refresh=True)

    async def inform_mutation(self, pk: uuid.UUID) -> None:
        await self.update(
            pk,
            # remove render, as they are not actual anymore:
            schemas.SceneUpdate(files=[]),
            updated_at=datetime.now(timezone.utc),
        )

    async def check_update_rights(
        self,
        instance: schemas.SceneExtended,
        payload: schemas.SceneUpdate | None,
    ) -> bool:
        if payload and payload.project_id:
            if not await self.db.projects.check_update_rights(
                instance.project,
                payload=None,
            ):
                return False
        return await super().check_update_rights(instance, payload)


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
        # HACK Element table does not have these fields:
        extra_values.pop("created_by_id", None)
        extra_values.pop("updated_by_id", None)
        data = super()._use_payload(payload, **extra_values)

        if payload:
            data["_json"] = payload.model_dump(exclude_unset=True)
        return data

    # NOTE no ORDER BY statement for Elements
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

    async def get(self, scene_id: uuid.UUID, filters: schemas.ElementsFilters):
        # verify scene existence and read access rights:
        scene = await self.db.scenes_simplified.get(scene_id)

        # fetch els:
        next_sync_token = time.time()
        items: list[schemas.Element] = await self.get_where(
            clauses=[
                self.model._scene_id == scene_id,
                self.model._updated > filters.sync_token,
            ],
        )
        return schemas.ReconcileElementsResponse.model_construct(
            items=items,
            next_sync_token=next_sync_token,
        )

    async def reconcile(
        self,
        scene_id: uuid.UUID,
        payload: schemas.SyncElementsRequest,
        filters: schemas.ElementsFilters,
    ):
        # NOTE
        # using lock per scene to ensure there no other client updated while
        # this update is performing, otherwise this client would
        # loose other client updates as 'next_sync_token' is defined
        # only after all current update will be handled (not before in order to not
        # respond with the same elements on next reconcile request)
        # FIXME
        # implement lock via database (ie SELECT scene FOR UPDATE)
        # because there are might be several app instances...
        self.app.state.scene_locks.setdefault(scene_id, asyncio.Lock())
        lock = self.app.state.scene_locks[scene_id]
        if lock.locked():
            self.logger.warning("Scene is locked. Wait for release.")
        async with lock:
            return schemas.ReconcileElementsResponse.model_construct(
                items=await self._reconcile(scene_id, payload, filters),
                next_sync_token=time.time(),
            )

    async def _reconcile(
        self,
        scene_id: uuid.UUID,
        payload: schemas.SyncElementsRequest,
        filters: schemas.ElementsFilters,
    ):
        # verify scene existence and read access rights:
        scene = await self.db.scenes_simplified.get(scene_id)

        # fetch els:
        payload_els = {el.id: el for el in payload.items}
        items = await self.db.elements.get_where(
            clauses=[
                self.model._scene_id == scene_id,
                or_(
                    # using payload element ids and db updated timestamp to:
                    # - to get elements to merge with payload
                    # - te get fresh elements to respond
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
        has_updates = False
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

            # NOTE
            # 2 clients have made update for the same element
            # - one client update has been stored already
            # - another client change just has come
            # - figure out who made last update on client side
            if payload_el.updated < current_el.updated:
                # extend respond items with element to update on client side
                respond_els[element_id] = current_el
                continue

            has_updates = True
            await self.pending_update((scene_id, element_id), payload_el)

        # append new
        for el in new_els.values():
            has_updates = True
            await self.pending_create(el, _scene_id=scene_id)

        if has_updates:
            # update rights for current scene is verified here internally:
            await self.db.scenes_simplified.inform_mutation(scene_id)

        await self.session.flush()
        return list(respond_els.values())

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


class FileToSceneRepository(
    ServiceRepositoryBase[
        models.FileToSceneAssociation,
        schemas.FileToSceneInternal,
        schemas.FileToSceneInternal,
        Never,
    ],
):
    model = models.FileToSceneAssociation
    schema = schemas.FileToSceneInternal


@dataclass(kw_only=True)
class DatabaseRepositories:
    all: Annotated[CommonSQLAlchemyRepository, Depends()]

    projects: Annotated[ProjectRepository, Depends()]
    scenes: Annotated[SceneRepository, Depends()]
    scenes_simplified: Annotated[SceneSimplifiedRepository, Depends()]
    elements: Annotated[ElementRepository, Depends()]
    files: Annotated[FileRepository, Depends()]
    files_to_scenes: Annotated[FileToSceneRepository, Depends()]

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
