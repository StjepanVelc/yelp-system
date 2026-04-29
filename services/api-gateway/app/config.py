from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    business_service_url: str = "http://localhost:8001"
    recommendation_service_url: str = "http://localhost:8002"
    ingestion_service_url: str = "http://localhost:8003"
    user_service_url: str = "http://localhost:8004"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "yelp-auth"
    jwt_audience: str = "yelp-api"
    jwt_leeway_seconds: int = 5
    jwt_roles_claim: str = "roles"

    business_required_roles: str = "business:read"
    recommendation_required_roles: str = "recommendation:read"

    user_status_path_template: str = "/users/{user_id}/status"
    user_status_timeout_seconds: float = 3.0

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
