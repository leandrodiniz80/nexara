from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Elevel Prospect AI"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str
    REDIS_URL: str

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    BACKEND_CORS_ORIGINS: list[str] = []


settings = Settings()
