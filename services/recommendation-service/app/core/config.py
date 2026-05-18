import os
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _resolve_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "yelp")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "change_me")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: Optional[str] = None
    business_service_grpc: str = "localhost:50051"
    redis_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_seconds: float = 0.2
    cache_rollout_percent: int = 100
    cache_shadow_mode: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_critical_settings(self):
        if not self.database_url:
            self.database_url = _resolve_database_url()

        if not self.database_url:
            raise ValueError("DATABASE_URL is required")

        if self.app_env.lower() in {"production", "staging"} and "change_me" in self.database_url:
            raise ValueError("DATABASE_URL contains placeholder value in non-development environment")
        return self


settings = Settings()

