from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """OnlyOffice DocumentServer configuration settings."""

    LOG_LEVEL: str = "INFO"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    # OnlyOffice DocumentServer settings
    BASE_URL: str = "http://localhost"
    UPLOAD_ENDPOINT: str = "/example/upload"
    USER_ID: str = "uid-1"
    LANGUAGE: str = "en"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


# Create a singleton instance
settings = AppConfig()
