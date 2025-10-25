import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    LOG_LEVEL: str = "INFO"

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-3-5-sonnet-20241022"

    # Medusa API Configuration
    MEDUSA_API_URL: str = "http://localhost:9000"
    MEDUSA_ADMIN_EMAIL: str = "admin@example.com"
    MEDUSA_ADMIN_PASSWORD: str = "supersecret"

    # Database settings
    DATABASE_URL: str = "postgresql://medusa:medusa@localhost:5432/medusa"

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379"

    # File paths
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.ANTHROPIC_API_KEY and self.ANTHROPIC_API_KEY.strip():
            os.environ["ANTHROPIC_API_KEY"] = self.ANTHROPIC_API_KEY


# Create a singleton instance
settings = AppConfig()
