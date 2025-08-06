from enum import StrEnum
from pathlib import Path
from typing import Literal

import sqlalchemy
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from common.config.config import LogLevel, VerboseModel
from common.schemas.base import URL


class AsyncDatabaseDriver(StrEnum):
    SQLITE = "sqlite+aiosqlite"
    POSTGRES = "postgresql+asyncpg"


class AppSettings(BaseSettings, VerboseModel):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OBJECTIVE_",
        env_file_encoding="utf-8",
        #
        arbitrary_types_allowed=True,
        validate_default=True,
        validate_return=True,
        frozen=True,
        extra="allow",
    )

    SERVICE_DIR: Path = Path(__file__).resolve().parent.parent

    APP_ENVIRONMENT: Literal["dev", "staging", "production"]

    APP_NAME: str = "Objective"
    APP_DESCRIPTION: str = "Plan your shooting objectively"
    APP_VERSION: str = "1.0.0.0"

    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"
    APP_WORKERS: int | None = None
    APP_RELOAD: bool = False

    APP_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    APP_RAISE_SERVER_EXCEPTIONS: bool | list[int] = False  # for debugging only
    APP_VERBOSE_EXCEPTIONS: bool = True
    APP_DEBUG_FREEZE: float | None = None

    API_PREFIX: URL = "/api"

    @property
    def API_OPENAPI_URL(self):
        return self.API_PREFIX / "openapi.json"

    @property
    def API_DOCS_URL(self):
        return self.API_PREFIX / "docs"

    API_SWAGGER_UI_PARAMS: dict = {
        "persistAuthorization": True,
        "withCredentials": True,
    }

    HTTP_SESSION_TIMEOUT: float = 59.0  # seconds

    SENTRY_DSN: SecretStr | None = ""
    SENTRY_ENVIRONMENT: Literal["dev", "staging", "production"] = "dev"
    SENTRY_TRACING: bool = False
    SENTRY_CA_CERTS: str | None = None
    SENTRY_DASHBOARD_URL: URL | None = None

    @property
    def SENTRY_RELEASE(self):
        return (
            f"{self.APP_NAME}@{self.APP_VERSION}" if self.APP_VERSION else self.APP_NAME
        )

    DATABASE_DRIVER: AsyncDatabaseDriver
    DATABASE_USER: SecretStr
    DATABASE_PASSWORD: SecretStr
    DATABASE_HOST: str | None
    DATABASE_PORT: int | None
    DATABASE_NAME: str

    @property
    def DATABASE_URL(self):
        return sqlalchemy.URL.create(
            drivername=self.DATABASE_DRIVER,
            username=(
                self.DATABASE_USER.get_secret_value() if self.DATABASE_USER else None
            ),
            password=(
                self.DATABASE_PASSWORD.get_secret_value()
                if self.DATABASE_PASSWORD
                else None
            ),
            host=self.DATABASE_HOST,
            port=self.DATABASE_PORT,
            database=self.DATABASE_NAME,
        )

    @property
    def DATABASE_URL_STR(self):
        return self.DATABASE_URL.render_as_string(hide_password=False)

    DATABASE_ECHO: bool = False
    DATABASE_ECHO_POOL: bool = False

    @property
    def ALEMBIC_INI_PATH(self):
        return self.SERVICE_DIR / "alembic.ini"

    USERS_SECRET: SecretStr = Field(min_length=10)
    USERS_TOKEN_LIFETIME: int = 3600 * 24 * 14  # 14 days

    @property
    def USERS_INITIAL_SCENES(self) -> list[Path]:
        return [
            self.SERVICE_DIR / "data/scenes/ParisTexas.objective",
            self.SERVICE_DIR / "data/scenes/Sicario.objective",
        ]

    LOG_LEVEL: LogLevel = LogLevel.INFO
    LOG_HANDLERS: list[str] = ["console", "file"]

    LOG_LEVEL_DOTENV: LogLevel = LogLevel.ERROR
    LOG_LEVEL_ALEMBIC: LogLevel = LogLevel.INFO
    LOG_LEVEL_SQLALCHEMY: LogLevel = LogLevel.WARNING
    LOG_LEVEL_PYTEST: LogLevel = LogLevel.DEBUG

    LOG_FILE: str = "objective.log"
    LOG_JSON_FILE: str = "objective.json"
    LOG_MAX_BYTE_WHEN_ROTATION: int = 100 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 10

    LOG_DIR_CREATE: bool = True

    @property
    def LOG_DIR(self):
        return self.SERVICE_DIR / "log"

    @property
    def LOGGING(self):
        default_handlers = {
            "console": {
                "level": self.LOG_LEVEL,
                "class": "logging.StreamHandler",
                "formatter": "console",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "level": self.LOG_LEVEL,
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "file",
                #
                "filename": self.LOG_DIR / self.LOG_FILE,
                "maxBytes": self.LOG_MAX_BYTE_WHEN_ROTATION,
                "backupCount": self.LOG_BACKUP_COUNT,
            },
        }
        handlers = {k: v for k, v in default_handlers.items() if k in self.LOG_HANDLERS}
        config = {
            "version": 1,
            "formatters": {
                "file": {
                    "()": "uvicorn.logging.ColourizedFormatter",
                    "format": "[-] %(asctime)s [%(levelname)s] - %(message)s",
                },
                "console": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    # "fmt": "%(levelprefix)s %(message)s",
                    "fmt": "%(levelprefix)s %(message)s",
                    "use_colors": None,
                },
            },
            "handlers": handlers,
            "loggers": {
                "app": {
                    "level": self.LOG_LEVEL,
                    "handlers": self.LOG_HANDLERS,
                },
                "common": {
                    "level": self.LOG_LEVEL,
                    "handlers": self.LOG_HANDLERS,
                },
                #
                #
                "dotenv": {
                    "level": self.LOG_LEVEL_DOTENV,
                    "handlers": self.LOG_HANDLERS,
                },
                "uvicorn": {
                    "handlers": self.LOG_HANDLERS,
                    "level": self.LOG_LEVEL,
                },
                "uvicorn.access": {
                    "handlers": self.LOG_HANDLERS,
                    "level": LogLevel.WARNING,  # also using custom as JournalMiddleware
                },
                "alembic": {
                    "level": self.LOG_LEVEL_ALEMBIC,
                    "handlers": self.LOG_HANDLERS,
                },
                "sqlalchemy": {
                    "level": self.LOG_LEVEL_SQLALCHEMY,
                    "handlers": self.LOG_HANDLERS,
                },
                "conftest": {
                    "level": self.LOG_LEVEL_PYTEST,
                    "handlers": self.LOG_HANDLERS,
                },
            },
        }
        return config
