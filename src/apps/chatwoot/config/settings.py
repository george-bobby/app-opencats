import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    POSTGRES_DATABASE: str = "chatwoot"
    POSTGRES_USERNAME: str = "postgres"
    POSTGRES_PASSWORD: str = "123"

    # Chatwoot configuration
    CHATWOOT_URL: str = "http://localhost:3000"
    CHATWOOT_ADMIN_EMAIL: str = "admin@acme.inc"
    CHATWOOT_ADMIN_PASSWORD: str = "Admin@123"

    # Redis configuration
    REDIS_PASSWORD: str = ""

    # API Keys
    OPENAI_API_KEY: str = ""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_THEME_SUBJECT: str = "SaaS company"
    COMPANY_NAME: str = "Acme Inc."
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    DEFAULT_ACCOUNT_ID: str = "1"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def model_dump_str(self):
        dump = self.model_dump()
        return {k: str(v) for k, v in dump.items()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = Config()  # type: ignore
