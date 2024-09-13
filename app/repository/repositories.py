from dataclasses import dataclass, fields
from logging import Logger
from typing import TYPE_CHECKING, Annotated, Generic, Never, Self, Sequence
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


# NOTE: Specific for Objective service only (not common)
# TODO move to service
class RepositoryBase(
    SQLAlchemyRepository,
    Generic[_ModelType, _SchemaType, _CreateSchemaType, _UpdateSchemaType],
):
    def _use_filter(self, filter_: schemas.FiltersBase | None, **extra_filters) -> dict:
        if filter_:

            # default filters:
            if "is_deleted" not in filter_.model_fields_set:
                filter_.is_deleted = False
            if "created_by_id" not in filter_.model_fields_set:
                filter_.created_by_id = self.current_user.id

            # filters modifications:
            if filter_.created_by_id == "":
                filter_ = filter_.model_remake(_self_exclude={"created_by_id"})
            if filter_.created_by_id == "current_user":
                filter_.created_by_id = self.current_user.id

        return super()._use_filter(filter_, **extra_filters)

    async def update(
        self,
        pk: UUID,
        payload: _UpdateSchemaType | None = None,
        options: Sequence[ORMOption] = _CLASS_DEFAULT,
        flush: bool = False,
        **extra_values,
    ) -> _SchemaType:

        # check rights
        res = await super().update(pk, payload, options, flush, **extra_values)
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
            #
            # scene files
            selectinload(models.Project.scenes)
            .selectinload(models.Scene.files)
            .load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
        ]

    # DEPRECATED
    DEFAULT_PROJECT_NAME = "Examples"
    DEFAULT_SCENE_NAME = "Untitled Scene"

    @deprecated("")
    async def create_default(self) -> schemas.Project:
        initial = self.app.state.initial_scenes
        scenes = [
            models.Scene(
                name=scene.app_state.get("name") or self.DEFAULT_SCENE_NAME,
                created_by_id=self.current_user.id,  # ex 'user_id'
                files=[
                    models.File(
                        created_by_id=self.current_user.id,  # ex 'user_id'
                        **f.model_dump(),
                    )
                    for f in scene.files.values()
                ],
                **scene.model_dump(exclude={"files"}),
            )
            for scene in initial
        ]

        return await self.create(
            schemas.ProjectCreate(name=self.DEFAULT_PROJECT_NAME),
            scenes=scenes,
        )


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
            #
            # files simplified
            selectinload(models.Scene.files).load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
        ]


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


@dataclass(kw_only=True)
class DatabaseRepositories:
    all: Annotated[CommonSQLAlchemyRepository, Depends()]

    projects: Annotated[ProjectRepository, Depends()]
    scenes: Annotated[SceneRepository, Depends()]
    files: Annotated[FileRepository, Depends()]

    users: Annotated[UserRepository, Depends()]

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
    def repositories(self) -> list[SQLAlchemyRepository]:
        return [getattr(self, field.name) for field in fields(self)]


DatabaseRepositoriesDepends = Annotated[DatabaseRepositories, Depends()]
