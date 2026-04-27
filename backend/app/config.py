from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://paytopay:paytopay@localhost:5432/paytopay"
    sync_database_url: str = "postgresql+psycopg2://paytopay:paytopay@localhost:5432/paytopay"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key"
    idempotency_ttl_hours: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
