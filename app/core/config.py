from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "monitoring-mvp"
    app_env: str = "local"
    app_debug: bool = True
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/monitoring"
    monitor_interval_seconds: int = 60
    request_timeout_seconds: int = 5
    check_results_retention_days: int = 30
    retention_cleanup_interval_hours: int = 24
    retention_delete_batch_size: int = 5000
    notification_backend: str = "log"
    notification_webhook_url: str | None = None
    notification_timeout_seconds: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
