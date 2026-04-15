from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:stipe245gaba@localhost:5432/yelp"
    business_service_grpc: str = "localhost:50051"

    model_config = {"env_file": ".env"}


settings = Settings()

