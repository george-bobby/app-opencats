from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    # Additional custom settings
    LOG_LEVEL: str = "INFO"
    DATA_PATH: Path = Path(__file__).parent.parent.joinpath("data")
    ANTHROPIC_API_KEY: str = "DUMMY"
    DATA_THEME_SUBJECT: str = "US-based Pet Supplies eCommerce Store"
    SPREE_URL: str = "http://localhost:3000"
    SPREE_STORE_NAME: str = "Fuzzloft"
    SPREE_ADMIN_EMAIL: str = "admin@fuzzloft.com"
    SPREE_ADMIN_PASSWORD: str = "spree123"
    # Use password `spree123`
    SPREE_ENCRYPTED_PASSWORD: str = "a7875e24432b2d7c3a177c2416dc3ea408410af701a1f29716467ebba3d6bccb33bc36c2f52a9ddf4f981c3c2208dc33ac45f10283f63b64fff95e3b47755af7"
    SPREE_PASSWORD_SALT: str = "wgxie3hyfPResx1h92b4"
    SECRET_KEY_BASE: str = "3cfb4b8bc12ea472087e3eaa0e01ca3aa89d038de01cf84d7d91e3893e6da98b46b462855ec53bf8fb031f9c02295d86ce5c128efd0a5d84b32d3d8cb787a8d6"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "spreecommerce"
    POSTGRES_DB: str = "spree"
    APP_POSTGRES_HOST: str = "localhost"
    APP_POSTGRES_PORT: int = 5432
    RAILS_DEVELOPMENT_HOSTS: str = "localhost,127.0.0.1,spree.localhost,spree.test"
    MAX_CONCURRENT_GENERATION_REQUESTS: int = 16
    PEXELS_API_KEYS: str = (
        "7ELaNO97Lac8GQAUnEeKh36xOki7HTLWRykhFmTPdVDB8F1VAv59IvSa,3rsXNughX5eDyXrKHPusCL9vxUQFFAAmKoEmI6okcFYbS2zLMmifqS7X,AOs3lLgIXxiyciKKaCT6jUSTSZuswQF1yI0VC5z7mUYduc93I6wvphcT"
    )

    model_config = SettingsConfigDict(
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
settings = Config()  # type: ignore
