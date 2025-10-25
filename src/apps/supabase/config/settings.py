import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Disable httpx info logging
logging.getLogger("httpx").setLevel(logging.WARNING)


class AppConfig(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """

    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str = "DUMMY_KEY"
    DATA_THEME_SUBJECT: str = "Consumer Goods & Retail"

    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")

    # Supabase Database Configuration
    POSTGRES_HOST: str = "db"
    LOCAL_POSTGRES_HOST: str = "localhost"
    POSTGRES_DB: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_PASSWORD: str = "your-super-secret-and-long-postgres-password"
    POSTGRES_USER: str = "supabase_admin.your-tenant-id"

    # Supabase Authentication
    JWT_SECRET: str = "your-super-secret-jwt-token-with-at-least-32-characters-long"
    JWT_EXPIRY: int = 3600
    ANON_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"  # noqa: E501
    SERVICE_ROLE_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q"  # noqa: E501
    DASHBOARD_USERNAME: str = "supabase"
    DASHBOARD_PASSWORD: str = "Admin@123"
    SECRET_KEY_BASE: str = "UpNVntn3cDxHJpq99YMc1T1AQgQpc8kfYTuRgBiYa15BLrx8etQoXz3gZv1/u2oq"
    VAULT_ENC_KEY: str = "your-encryption-key-32-chars-min"

    # Database Pooler Configuration
    POOLER_PROXY_PORT_TRANSACTION: int = 6543
    POOLER_DEFAULT_POOL_SIZE: int = 20
    POOLER_MAX_CLIENT_CONN: int = 100
    POOLER_TENANT_ID: str = "your-tenant-id"

    # API Configuration
    KONG_HTTP_PORT: int = 8000
    KONG_HTTPS_PORT: int = 8443
    PGRST_DB_SCHEMAS: str = "public,storage,graphql_public"

    # Auth Configuration
    SITE_URL: str = "http://localhost:3000"
    ADDITIONAL_REDIRECT_URLS: str = ""
    API_EXTERNAL_URL: str = "http://localhost:8000"
    DISABLE_SIGNUP: bool = False

    # Mailer Configuration
    MAILER_URLPATHS_CONFIRMATION: str = "/auth/v1/verify"
    MAILER_URLPATHS_INVITE: str = "/auth/v1/verify"
    MAILER_URLPATHS_RECOVERY: str = "/auth/v1/verify"
    MAILER_URLPATHS_EMAIL_CHANGE: str = "/auth/v1/verify"

    # Email Configuration
    ENABLE_EMAIL_SIGNUP: bool = True
    ENABLE_EMAIL_AUTOCONFIRM: bool = False
    SMTP_ADMIN_EMAIL: str = "admin@example.com"
    SMTP_HOST: str = "supabase-mail"
    SMTP_PORT: int = 2500
    SMTP_USER: str = "fake_mail_user"
    SMTP_PASS: str = "fake_mail_password"
    SMTP_SENDER_NAME: str = "fake_sender"
    ENABLE_ANONYMOUS_USERS: bool = False

    # Phone Configuration
    ENABLE_PHONE_SIGNUP: bool = True
    ENABLE_PHONE_AUTOCONFIRM: bool = True

    # Studio Configuration
    STUDIO_DEFAULT_ORGANIZATION: str = "Default Organization"
    STUDIO_DEFAULT_PROJECT: str = "Default Project"
    STUDIO_PORT: int = 3000
    SUPABASE_PUBLIC_URL: str = "http://localhost:8000"
    IMGPROXY_ENABLE_WEBP_DETECTION: bool = True

    # Functions Configuration
    FUNCTIONS_VERIFY_JWT: bool = False

    # Analytics Configuration
    LOGFLARE_PUBLIC_ACCESS_TOKEN: str = "your-super-secret-and-long-logflare-key-public"
    LOGFLARE_PRIVATE_ACCESS_TOKEN: str = "your-super-secret-and-long-logflare-key-private"
    DOCKER_SOCKET_LOCATION: str = "/var/run/docker.sock"
    GOOGLE_PROJECT_ID: str = "GOOGLE_PROJECT_ID"
    GOOGLE_PROJECT_NUMBER: str = "GOOGLE_PROJECT_NUMBER"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.joinpath(".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY

    def model_dump_str(self):
        return {k: str(v) for k, v in self.model_dump().items()}


# Create a singleton instance
settings = AppConfig()  # type: ignore
