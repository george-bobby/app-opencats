import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """

    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str = "DUMMY"
    GENAI_API_KEY: str = "DUMMY"

    DEFAULT_MODEL: str = "gpt-4.1-mini-2025-04-14"
    MAX_OUTPUT_TOKENS: int = 32_768

    DATA_THEME_SUBJECT: str = "Consumer Goods & Retail"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    ODOO_URL: str = "http://localhost:8069"
    ODOO_DB: str = "odoo"
    ODOO_USERNAME: str = "admin"
    ODOO_PASSWORD: str = "admin"

    COMPANY_NAME: str = "Modern Market Co."
    COMPANY_DOMAIN: str = "modernmarket.co"
    COMPANY_LOGO: Path = Path(__file__).parent.parent.joinpath("data/logo.png")
    USER_PASSWORD: str = ""
    DATABASE_PATH: str = "./data/database.sqlite"
    SYSTEM_USER: str = "Bob Smith"

    # Threading configuration
    MAX_THREADS: int | None = 1  # None means auto-detect optimal threads
    DISABLE_THREADING: bool = False  # Force single-threaded processing

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
        os.environ["GENAI_API_KEY"] = self.GENAI_API_KEY


# Create a singleton instance
settings = AppConfig()  # type: ignore
