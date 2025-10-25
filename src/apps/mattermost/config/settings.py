from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """

    LOG_LEVEL: str = "INFO"
    TZ: str = "UTC"

    ANTHROPIC_API_KEY: str = "DUMMY"
    DEFAULT_MODEL: str = "claude-3-5-haiku-latest"
    MAX_OUTPUT_TOKENS: int = 8192

    MAX_GENERATE_RETRIES: int = 3
    MAX_THREADS: int = 32

    DATA_THEME_SUBJECT: str = "US-based Technology & Professional Services SMB, it provides software products, IT systems, integrations, or service delivery"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    MATTERMOST_URL: str = "http://localhost:8065"
    MATTERMOST_EMAIL: str = "admin@vertexon.com"
    MATTERMOST_OWNER_USERNAME: str = "john.appleseed"
    MATTERMOST_OWNER_FIRST_NAME: str = "John"
    MATTERMOST_OWNER_LAST_NAME: str = "Appleseed"
    MATTERMOST_OWNER_NICKNAME: str = "Johnny"
    MATTERMOST_OWNER_POSITION: str = "Executive Manager"
    MATTERMOST_PASSWORD: str = "password@123"

    COMPANY_DOMAIN: str = "vertexon.com"

    POSTGRES_USERNAME: str = "mmuser"
    POSTGRES_PASSWORD: str = "mmuser_password"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    POSTGRES_DATABASE: str = "mattermost"

    COMPANY_NAME: str = ""
    USER_PASSWORD: str = ""
    DATABASE_PATH: str = "./data/database.sqlite"
    SYSTEM_USER: str = ""

    MATTERMOST_IMAGE: str = "mattermost-enterprise-edition"
    MATTERMOST_IMAGE_TAG: str = "10.11"
    POSTGRES_IMAGE_TAG: str = "13-alpine"
    RESTART_POLICY: str = "unless-stopped"
    MATTERMOST_CONTAINER_READONLY: bool = False

    APP_PORT: int = 8065
    CALLS_PORT: int = 8000
    HTTP_PORT: int = 80
    HTTPS_PORT: int = 443

    # Docker environment variables
    POSTGRES_USER: str = "mmuser"
    POSTGRES_PASSWORD: str = "mmuser_password"
    POSTGRES_DB: str = "mattermost"

    MAX_CONCURRENT_GENERATION_REQUESTS: int = 32

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def model_dump_str(self):
        dump = self.model_dump()
        return {k: str(v) for k, v in dump.items()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# Create a singleton instance
settings = AppConfig()  # type: ignore
