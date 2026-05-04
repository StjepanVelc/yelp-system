from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    redis_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_seconds: float = 0.2
    cache_rollout_percent: int = 100
    cache_shadow_mode: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_critical_settings(self):
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")

        if self.app_env.lower() in {"production", "staging"} and "change_me" in self.database_url:
            raise ValueError("DATABASE_URL contains placeholder value in non-development environment")
        return self


settings = Settings()
