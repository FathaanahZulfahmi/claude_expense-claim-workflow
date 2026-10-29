from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# All application settings in one place. Values are read from environment
# variables (or the .env file) and validated by Pydantic at startup, so a
# bad or missing setting fails early instead of in the middle of a request.
class Settings(BaseSettings):
    app_name: str = Field(..., env="APP_NAME")

    # Optional here so the app can start (e.g. /health) without them;
    # the Claude service checks they are set before calling the API.
    # SecretStr hides the key in logs and reprs.
    anthropic_api_key: SecretStr | None = None
    claude_model: str | None = None
    claude_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    claude_max_retries: int = Field(default=2, ge=0, le=5)

    # MongoDB connection string (required) and database name.
    mongodb_uri: SecretStr
    mongodb_database: str = "expense_claims"

    log_level: str = "INFO"

    # Load from a .env file in the working directory; ignore unknown keys.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# lru_cache builds Settings only once; later calls return the same object.
@lru_cache
def get_settings() -> Settings:
    return Settings()
