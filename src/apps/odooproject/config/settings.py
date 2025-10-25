import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """

    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str
    DEFAULT_MODEL: str = "gpt-4o-mini-2024-07-18"
    MAX_OUTPUT_TOKENS: int = 16_384
    DATA_THEME_SUBJECT: str = "Consumer Goods & Retail"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    ODOO_URL: str = "http://localhost:8069"
    ODOO_DB: str = "odoo"
    ODOO_USERNAME: str = "admin"
    ODOO_PASSWORD: str = "admin"

    POSTGRES_USERNAME: str = "odoo"
    POSTGRES_PASSWORD: str = "odoo"
    POSTGRES_DATABASE: str = "odoo"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    COMPANY_NAME: str = "Modern Market Co."
    COMPANY_LOGO: Path = Path(__file__).parent.parent.joinpath("data/logo.png")
    USER_PASSWORD: str = ""
    DATABASE_PATH: str = "./data/database.sqlite"
    SYSTEM_USER: str = "Bob Smith"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = AppConfig()  # type: ignore
