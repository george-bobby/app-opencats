import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    API_URL: str = "http://localhost:8000"
    HELPDESK_COMPANY_ID: str = "1"
    ADMIN_USERNAME: str = "Administrator"
    ADMIN_PASSWORD: str = "admin"
    OPENAI_API_KEY: str = "DUMMY_KEY"
    DATA_THEME_SUBJECT: str = "a IT software development company"
    LIST_LIMIT: int = 100000
    COMPANY_NAME: str = "Acme Inc."
    COMPANY_ABBR: str = "AI"
    USER_PASSWORD: str = "acmeincuser"
    MYSQL_PASSWORD: str = "admin"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    COMPOSE_BAKE: str = "true"

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

    def model_dump_str(self):
        dump = self.model_dump()
        return {k: str(v) for k, v in dump.items()}

    @property
    def COMPANY_DOMAIN(self):  # noqa: N802
        company_name_clean = "".join(c for c in self.COMPANY_NAME if c.isalnum()).lower()
        return f"{company_name_clean}.com"


# Create a singleton instance
settings = Config()  # type: ignore
