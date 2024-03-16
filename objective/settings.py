import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings."""

    host: str = "127.0.0.1"
    port: int = 8000
    workers_count: int = 1  # quantity of workers for uvicorn
    reload: bool = False  # Enable uvicorn reloading
    environment: Literal["dev", "prod", "pytest"] = "dev"
    log_level: str | int = logging.DEBUG
    users_secret: SecretStr = Field(min_length=10)

    openapi_url: str = "/api/openapi.json"
    docs_url: str = "/api/docs"

    # Variables for the database
    db_host: str
    db_port: int
    db_user: str
    db_pass: SecretStr
    db_base: str
    db_echo: bool = False

    # Sentry
    sentry_dns: str | None = None
    sentry_env: Literal["dev", "staging", "production"] = "dev"
    sentry_tracing: bool = True
    sentry_url: str | None = None

    @property
    def db_url(self):
        return URL.create(
            drivername="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            username=self.db_user,
            password=self.db_pass.get_secret_value(),
            database=self.db_base,
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OBJECTIVE_",
        env_file_encoding="utf-8",
    )


settings = Settings()


# logger settings

FMT_STRING = (
    "%(levelprefix)s %(name)s [%(asctime)s] %(message)s"
    if settings.environment == "prod"
    else "%(levelprefix)s - %(message)s"
)

LOGGER_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": FMT_STRING,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "for_file": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": FMT_STRING,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": settings.log_level,
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "file": {
            "level": settings.log_level,
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "for_file",
            "filename": "logs/log_file.log",
            "maxBytes": 5000000,
            "backupCount": 10,
        },
    },
    "loggers": {
        "root": {
            "level": settings.log_level,
            "handlers": ["console", "file"],
        },
    },
}

dictConfig(LOGGER_CONFIG)

logging.getLogger("multipart").setLevel("INFO")
logging.getLogger("asyncio").setLevel("INFO")
logging.getLogger("passlib").setLevel("INFO")
