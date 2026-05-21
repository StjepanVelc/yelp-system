from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"

    kafka_bootstrap_servers: str = "kafka:9092"
    cdc_topic_prefix: str = "yelp"
    cdc_consumer_group: str = "yelp-cdc-consumer"
    cdc_auto_offset_reset: str = "latest"
    cdc_poll_timeout_ms: int = 1000

    redis_url: str = "redis://:dev_redis_pass@redis:6379/0"
    redis_timeout_seconds: float = 0.2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
