import logging
import logging.config
import os

import click
import sentry_sdk
import uvicorn
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.applications.objective import ObjectiveAPP
from app.config import AppSettings

logger = logging.getLogger("app.main")


def setup_logging(settings: AppSettings) -> None:
    # return
    if settings.LOG_DIR_CREATE and not settings.LOG_DIR.exists():
        settings.LOG_DIR.mkdir()
    logging.config.dictConfig(settings.LOGGING)


def setup_sentry(settings: AppSettings) -> None:
    if settings.SENTRY_DSN:
        logger.info("Setup Sentry. Environment: %s", settings.SENTRY_ENVIRONMENT)
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN.get_secret_value(),
            ca_certs=settings.SENTRY_CA_CERTS,
            release=settings.SENTRY_RELEASE,
            environment=settings.SENTRY_ENVIRONMENT,
            enable_tracing=settings.SENTRY_TRACING,
            attach_stacktrace=True,
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )


def setup_database(settings: AppSettings) -> None:
    pass


def setup(settings: AppSettings | None = None) -> ObjectiveAPP:
    settings = settings or AppSettings()

    # call for setup for each worker process
    setup_logging(settings)
    setup_sentry(settings)
    setup_database(settings)

    logger.info(
        "Run app worker [%s]",
        click.style(os.getpid(), fg="cyan", bold=True),
    )
    return ObjectiveAPP.startup(settings)


def main() -> None:
    settings = AppSettings()

    # setup logging for main process
    setup_logging(settings)
    logger.info("Run %s (%s)", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Settings: %s", settings)
    logger.debug("Other env variables: %s", settings.model_extra)

    uvicorn.run(
        "app.main:setup",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        workers=settings.APP_WORKERS,
        reload=settings.APP_RELOAD,
        factory=True,
        log_config=None,
    )


if __name__ == "__main__":
    main()
