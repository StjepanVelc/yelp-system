import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:stipe245gaba@localhost:5432/yelp"

    model_config = {"env_file": ".env"}


settings = Settings()
