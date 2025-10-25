import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """

    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str
    DEFAULT_MODEL: str = "gpt-4o-mini"
    DATA_THEME_SUBJECT: str = "Consumer Goods & Retail"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    ODOO_URL: str = "http://localhost:8069"
    ODOO_DB: str = "odoo"
    ODOO_USERNAME: str = "admin"
    ODOO_PASSWORD: str = "admin"

    COMPANY_NAME: str = ""
    USER_PASSWORD: str = ""
    DATABASE_PATH: str = "./data/database.sqlite"
    SYSTEM_USER: str = ""

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
