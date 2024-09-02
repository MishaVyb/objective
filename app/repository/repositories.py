from dataclasses import dataclass, fields
from logging import Logger
from typing import TYPE_CHECKING, Annotated, Never, Self

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing_extensions import deprecated

from app.config import AppSettings
from app.repository.base.sqlalchemy import (
    CommonSQLAlchemyRepository,
    StrongInstanceIdentityMap,
)
from app.repository.users import UserRepository

from . import models, schemas
from .base.sqlalchemy import SQLAlchemyRepository

if TYPE_CHECKING:
    from app.dependencies.dependencies import AuthenticatedUser
else:
    AuthenticatedUser = object


class ProjectRepository(
    SQLAlchemyRepository[
        models.Project,
        schemas.Project,
        schemas.ProjectCreate,
        schemas.ProjectUpdate,
    ],
):
    model = models.Project
    schema = schemas.Project

    class Loading(SQLAlchemyRepository.Loading):
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
    async def create_default(self, request: Request | None = None):
        initial: list[
            schemas.SceneJsonFilePersistence
        ] = request.app.state.initial_scenes
        scenes = [
            models.Scene(
                name=scene.app_state.get("name") or self.DEFAULT_SCENE_NAME,
                user_id=self.user.id,
                files=[
                    models.File(
                        user_id=self.user.id,
                        **f.model_dump(),
                    )
                    for f in scene.files.values()
                ],
                **scene.model_dump(exclude={"files"}),
            )
            for scene in initial
        ]

        return await self.create(
            schemas.SceneCreate(name=self.DEFAULT_PROJECT_NAME),
            scenes=scenes,
        )


class SceneRepository(
    SQLAlchemyRepository[
        models.Scene,
        schemas.SceneSimplified,
        schemas.SceneExtended,
        schemas.SceneExtended,
    ],
):
    model = models.Scene
    schema = schemas.SceneSimplified

    class Loading(SQLAlchemyRepository.Loading):
        default = [
            #
            # files simplified
            selectinload(models.Scene.files).load_only(
                *models.File.columns_depending_on(schemas.FileSimplified),
                raiseload=True,
            ),
        ]


class FileRepository(
    SQLAlchemyRepository[
        models.File,
        schemas.FileSimplified,
        schemas.FileCreate,
        Never,
    ],
):
    model = models.File
    schema = schemas.FileSimplified


@dataclass(kw_only=True)
class DatabaseRepositories:
    all: Annotated[CommonSQLAlchemyRepository, Depends()]

    projects: Annotated[ProjectRepository, Depends()]
    scenes: Annotated[SceneRepository, Depends()]
    files: Annotated[FileRepository, Depends()]

    # NOTE
    # no users repository here as it fails to circular imports
    users: Annotated[UserRepository, Depends()]

    @classmethod
    def construct(
        cls,
        session: AsyncSession,
        settings: AppSettings,
        logger: Logger,
        current_user: AuthenticatedUser,
    ) -> Self:
        # storage shared between all repositories for single session
        storage = StrongInstanceIdentityMap(session)
        return cls(
            **{
                field.name: field.type(
                    session=session,
                    storage=storage,
                    settings=settings,
                    logger=logger,
                    current_user=current_user,
                )
                for field in fields(cls)
            }
        )

    @property
    def repositories(self) -> list[SQLAlchemyRepository]:
        return [getattr(self, field.name) for field in fields(self)]


DatabaseRepositoriesDepends = Annotated[DatabaseRepositories, Depends()]
