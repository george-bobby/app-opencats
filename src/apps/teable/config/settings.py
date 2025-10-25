import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    OPENAI_API_KEY: str | None = None
    DATA_THEME_SUBJECT: str = "a Marketing Agency that uses AI to help businesses grow"
    TEABLE_URL: str = "http://localhost:3000"
    TEABLE_ADMIN_EMAIL: str = "admin@summittech.com"
    TEABLE_ADMIN_PASSWORD: str = "Admin@123"

    # Database credentials
    POSTGRES_PASSWORD: str = "replace_this_password"
    REDIS_PASSWORD: str = "replace_this_password"
    SECRET_KEY: str = "replace_this_secret_key"

    # Public access
    PUBLIC_ORIGIN: str = "http://0.0.0.0:3000"

    # Postgres configuration
    POSTGRES_HOST: str = "teable-db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "teable"
    POSTGRES_USER: str = "teable"

    # Redis configuration
    REDIS_HOST: str = "teable-cache"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # App configuration
    BACKEND_CACHE_PROVIDER: str = "redis"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def PRISMA_DATABASE_URL(self) -> str:  # noqa: N802
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def BACKEND_CACHE_REDIS_URI(self) -> str:  # noqa: N802
        return f"redis://default:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    def model_dump_str(self):
        dump = self.model_dump()
        # Add computed properties to the dump
        dump["PRISMA_DATABASE_URL"] = self.PRISMA_DATABASE_URL
        dump["BACKEND_CACHE_REDIS_URI"] = self.BACKEND_CACHE_REDIS_URI
        return {k: str(v) for k, v in dump.items()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = Config()  # type: ignore
