from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки только из переменных окружения (в Docker — из infra/docker-compose + .env)."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+asyncpg://pmbi:pmbi@localhost:5432/pmbi"
    sync_database_url: str = "postgresql://pmbi:pmbi@localhost:5432/pmbi"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "pmbi"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    jwt_secret: str = "dev-secret-change-in-production-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()
