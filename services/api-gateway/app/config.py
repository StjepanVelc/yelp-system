from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    business_service_url: str = "http://localhost:8001"
    recommendation_service_url: str = "http://localhost:8002"
    ingestion_service_url: str = "http://localhost:8003"

    model_config = {"env_file": ".env"}


settings = Settings()
