import asyncio
import logging
from typing import Literal

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.schema import SchemaItem

from alembic import context
from app.config import AppSettings
from app.main import setup_database, setup_logging
from app.repository.models import Base

config = context.config
target_metadata = Base.metadata

logger = logging.getLogger("alembic.runtime.migration")

TYPES = Literal[
    "schema",
    "table",
    "column",
    "index",
    "unique_constraint",
    "foreign_key_constraint",
]


def include_object(
    item: SchemaItem,
    name: str | None,
    type: TYPES,
    reflected: bool,
    compare_to: SchemaItem | None,
):
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    logger.info("Running migrations against database: %s", connection.engine.url)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_async() -> None:
    # alembic called from CLI

    settings = config.attributes["app_settings"]
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        echo_pool=settings.DATABASE_ECHO_POOL,
    )
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)

    await engine.dispose()


def setup():
    settings = AppSettings()

    setup_logging(settings)
    setup_database(settings)

    logger.info("Run alembic migrations. ")
    logger.debug("Settings: %s", settings)

    config.attributes["app_settings"] = settings
    config.attributes["connection"] = None


if __name__ == "env_py":

    if not config.attributes.get("app_settings"):
        setup()

    if context.is_offline_mode():
        run_migrations_offline()

    if conn := config.attributes.get("connection"):
        # alembic called programmatically with sync connection
        run_migrations(conn)
    else:
        # alembic called from CLI
        asyncio.run(run_migrations_async())
