import logging
from pathlib import Path
from tempfile import gettempdir

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

TEMP_DIR = Path(gettempdir())


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    workers_count: int = 1  # quantity of workers for uvicorn
    reload: bool = False  # Enable uvicorn reloading
    environment: str = "dev"
    log_level: str | int = logging.DEBUG
    users_secret: SecretStr = Field(min_length=10)

    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "objective"
    db_pass: str = "objective"
    db_base: str = "objective"
    db_echo: bool = False

    @property
    def db_url(self):
        return URL.create(
            drivername="postgresql+asyncpg",
            host=self.db_host,
            port=self.db_port,
            username=self.db_user,
            password=self.db_pass,
            database=self.db_base,
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OBJECTIVE_",
        env_file_encoding="utf-8",
    )


logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.DEBUG)
settings = Settings()
