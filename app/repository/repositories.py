from dataclasses import dataclass, fields
from logging import Logger
from typing import TYPE_CHECKING, Annotated, Any, Never, Self, Sequence
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.interfaces import ORMOption
from typing_extensions import deprecated

from app.config import AppSettings
from app.repository.users import UserRepository
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


# NOTE: Specific for Objective service only (not common)
# TODO move to service
class RepositoryBase(
    SQLAlchemyRepository[_ModelType, _SchemaType, _CreateSchemaType, _UpdateSchemaType],
):
    db: "DatabaseRepositories"

    def _use_filters(
        self,
        filters: schemas.FiltersBase | None,
        *,
        is_deleted: bool = False,  # UNUSED using is_deleted flag from request Query
        **extra_filters,
    ) -> dict:
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

    async def update(
        self,
        pk: UUID,
        payload: _UpdateSchemaType | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        refresh: bool = False,
        **extra_values,
    ) -> _SchemaType:

        # check rights
        res = await super().update(pk, payload, options, flush, refresh, **extra_values)
        if self.current_user.id != res.created_by_id:
            raise NotEnoughRights(f"Not enough rights to update: {res}")

        return res

    async def pending_update(
        self, pk: UUID, payload: _UpdateSchemaType | None = None, **extra_values
    ) -> None:
        raise NotImplementedError


class ProjectRepository(
    RepositoryBase[
        models.Project,
        schemas.Project,
        schemas.ProjectCreate,
        schemas.ProjectUpdate,
    ],
):
    model = models.Project
    schema = schemas.Project

    class Loading(RepositoryBase.Loading):
        default = [
            #
            # scenes
            selectinload(models.Project.scenes).load_only(
                *models.Scene.columns_depending_on(schemas.SceneSimplified),
                raiseload=True,
            ),
            # #
            # # scene files
            # selectinload(models.Project.scenes)
            # .selectinload(modelsene.files)
            # .load_only(
            #     *models.File.columns_depending_on(schemas.FileSimplified),
            #     raiseload=True,
            # ),
        ]

    # DEPRECATED
    DEFAULT_PROJECT_NAME = "Examples"
    DEFAULT_SCENE_NAME = "Untitled Scene"

    @deprecated("")
    async def create_default(self) -> schemas.Project:
        initial = self.app.state.initial_scenes
        # scenes = [
        #     models.Scene(
        #         name=scene.app_state.get("name") or self.DEFAULT_SCENE_NAME,
        #         created_by_id=self.current_user.id,  # ex 'user_id'
        #         files=[
        #             models.File(
        #                 created_by_id=self.current_user.id,  # ex 'user_id'
        #                 **f.model_dump(),
        #             )
        #             for f in scene.files.values()
        #         ],
        #         **scene.model_dump(exclude={"files"}),
        #     )
        #     for scene in initial
        # ]

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
    RepositoryBase[
        models.Scene,
        schemas.SceneExtended,
        schemas.SceneCreate,
        schemas.SceneUpdate,
    ],
):
    model = models.Scene
    schema = schemas.SceneExtended

    class Loading(RepositoryBase.Loading):
        default = [
            joinedload(models.Scene.project),
            # #
            # # files simplified
            # selectinload(models.Scene.files).load_only(
            #     *models.File.columns_depending_on(schemas.FileSimplified),
            #     raiseload=True,
            # ),
        ]

    async def create(
        self,
        payload: schemas.SceneCreate,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        refresh: bool = False,
        **extra_values,
    ) -> schemas.SceneExtended:
        scene = await super().create(
            payload,
            options,
            refresh,
            **extra_values,
        )
        for file in payload.files:
            if not await self.db.files.exist_where(id=file.id):
                await self.db.files.create(file)
        return scene  # do not refresh instance as Scene has not target relationship with Files


class FileRepository(
    RepositoryBase[
        models.File,
        schemas.FileExtended,
        schemas.FileCreate,
        Never,
    ],
):
    model = models.File
    schema = schemas.FileExtended

    async def get(
        self, pk: UUID, *, options: Sequence[ORMOption] = ..., refresh: bool = False
    ) -> schemas.FileExtended:
        raise NotImplementedError  # use get_one by id instead


@dataclass(kw_only=True)
class DatabaseRepositories:
    all: Annotated[CommonSQLAlchemyRepository, Depends()]

    projects: Annotated[ProjectRepository, Depends()]
    scenes: Annotated[SceneRepository, Depends()]
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
    def repositories(self) -> list[RepositoryBase]:
        return [getattr(self, field.name) for field in fields(self)]


DatabaseRepositoriesDepends = Annotated[DatabaseRepositories, Depends()]
