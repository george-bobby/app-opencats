import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_THEME_SUBJECT: str = "a IT outsourcing company"
    LIST_LIMIT: int = 100000

    # API configuration
    API_URL: str = "http://localhost:8000"

    # HRMS configuration
    HRMS_COMPANY_ID: str = "1"

    # Admin credentials
    ADMIN_USERNAME: str = "Administrator"
    ADMIN_PASSWORD: str = "admin"

    # API Keys
    OPENAI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = Config()  # type: ignore
