import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    LOG_LEVEL: str = "INFO"
    GITLAB_URL: str = "http://localhost"
    GITLAB_TOKEN: str = "glpat-jEWJwoRqEbe-Y5CZSqXa"
    GITHUB_TOKEN: str = "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"
    DEBUG: bool = False

    # GitLab-specific settings
    CONTAINER_NAME: str = "gitlab-container"
    DOPPLER_TOKEN: str = ""

    # Database configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "gitlab"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.GITHUB_TOKEN:
            os.environ["GITHUB_TOKEN"] = self.GITHUB_TOKEN


# Create a singleton instance
settings = AppConfig()

# Repository mappings (replaces config.json)
REPOSITORY_MAPPINGS = {
    "simple-python-website": "https://github.com/darumor/simple-python-website",
    "bookstack": "https://github.com/BookStackApp/BookStack",
    "hello-world": "https://github.com/octocat/Hello-World",
    "license": "https://github.com/nexxeln/license-generator",
    "minGPT": "https://github.com/karpathy/minGPT",
    "superagi": "https://github.com/TransformerOptimus/SuperAGI",
    "tinyhttp": "https://github.com/tinyhttp/tinyhttp",
}


# Legacy compatibility functions
def load_env_config():
    """Load complete environment configuration"""
    return {"gitlab_url": settings.GITLAB_URL, "gitlab_token": settings.GITLAB_TOKEN, "github_token": settings.GITHUB_TOKEN, "debug": settings.DEBUG, "repositories": REPOSITORY_MAPPINGS}


def get_db_config():
    """Get database configuration as dictionary"""
    return {"host": settings.DB_HOST, "port": settings.DB_PORT, "database": settings.DB_NAME, "user": settings.DB_USER, "password": settings.DB_PASSWORD}


def load_config():
    """Load repository configurations from constants"""
    return REPOSITORY_MAPPINGS
