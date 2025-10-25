import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    OPENAI_API_KEY: str = "DUMMY"
    DATA_THEME_SUBJECT: str = "a photography studio that sells photography assets like Lightroom presets, Photoshop actions, etc."
    CUSTOM_DOMAIN: str = "gumroad.localhost"
    PROTOCOL: str = "http"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    GUMROAD_EMAIL: str = "seller@gumroad.com"
    GUMROAD_PASSWORD: str = "password"
    PEXELS_API_KEY: str = "7ELaNO97Lac8GQAUnEeKh36xOki7HTLWRykhFmTPdVDB8F1VAv59IvSa"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "gumroad"
    COMPOSE_BAKE: str = "true"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def GUMROAD_BASE_URL(self):  # noqa: N802
        return f"{self.PROTOCOL}://{self.CUSTOM_DOMAIN}"

    def model_dump_str(self):
        dump = self.model_dump()
        return {k: str(v) for k, v in dump.items()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY


# Create a singleton instance
settings = Config()  # type: ignore
