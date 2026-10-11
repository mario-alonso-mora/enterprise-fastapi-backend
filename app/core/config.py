from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise FastAPI"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://app:local-password@localhost:5432/enterprise"
    jwt_secret_key: SecretStr
    bootstrap_key: SecretStr
    jwt_issuer: str = "enterprise-fastapi"
    jwt_audience: str = "enterprise-fastapi-api"
    access_token_minutes: int = 30
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_login_per_minute: int = Field(default=5, ge=1)
    rate_limit_register_per_minute: int = Field(default=3, ge=1)
    rate_limit_refresh_per_minute: int = Field(default=10, ge=1)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment == "production":
            for name in ("jwt_secret_key", "bootstrap_key"):
                val = getattr(self, name).get_secret_value()
                if len(val) < 32 or "dev-only" in val or "replace" in val:
                    raise ValueError(f"{name} must be securely configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
