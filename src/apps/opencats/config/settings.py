"""OpenCATS application settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    LOG_LEVEL: str = "INFO"

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "claude-3-5-sonnet-20241022"

    # OpenCATS API Configuration
    OPENCATS_API_URL: str = "http://localhost:80"
    OPENCATS_ADMIN_EMAIL: str = "john@mycompany.net"
    OPENCATS_ADMIN_PASSWORD: str = "john99"
    OPENCATS_SITE_NAME: str = "CATS"

    # OpenCATS User Configuration
    OPENCATS_OWNER_ID: int = 1
    OPENCATS_RECRUITER_ID: int = 1

    # Database settings (for direct DB access if needed)
    DATABASE_URL: str = "mysql://dev:dev@localhost:3306/cats"

    # File paths
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    # Data generation settings
    DATA_THEME_SUBJECT: str = "a technology consulting company"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


settings = AppConfig()
