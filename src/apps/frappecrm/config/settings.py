import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_THEME_SUBJECT: str = "a IT outsourcing company"
    LIST_LIMIT: int = 100000
    COMPANY_NAME: str = "Acme Inc."
    USER_PASSWORD: str = "acmeincuser"

    # API configuration
    API_URL: str = "http://localhost:8000"

    # Admin credentials
    ADMIN_USERNAME: str = "Administrator"
    ADMIN_PASSWORD: str = "admin"

    # API Keys
    OPENAI_API_KEY: str = "DUMMY_KEY"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = Config()  # type: ignore
