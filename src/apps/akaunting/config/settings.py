from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_THEME_SUBJECT: str = "a Software company"

    # Akaunting API configuration
    API_URL: str = "http://localhost:8000"
    AKAUNTING_COMPANY_ID: str = "1"
    AKAUNTING_COMPANY_NAME: str = "Acme Inc"
    AKAUNTING_API_KEY: str = "f77f0d79-f38e-4f78-b7fe-0be1c4f4db14"

    # Admin credentials
    ADMIN_USERNAME: str = "johny.appleseed@acme.inc"
    ADMIN_PASSWORD: str = "1qaz2wsx"

    # Database configuration
    AKAUNTING_DB: str = "akaunting"
    AKAUNTING_DB_HOST: str = "db"
    AKAUNTING_DB_USER: str = "akaunting"
    AKAUNTING_DB_PASSWORD: str = "akaunting"

    # API Keys
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


# Create a singleton instance
settings = Config()  # type: ignore
