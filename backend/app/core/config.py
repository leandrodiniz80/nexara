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

    # Stripe is an optional feature toggle: empty defaults mean the platform
    # boots and runs fully without it (manual plan upgrades stay available).
    # Real keys must come from the environment/.env — never hardcoded here.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_ENTERPRISE: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/billing/success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/billing/cancel"
    # Sprint 280: where the Stripe Customer Portal sends the customer back
    # to after they finish managing their subscription — the spec's own
    # version hardcoded a literal placeholder domain ("seuapp.com")
    # straight into the router; a real setting instead, matching every
    # other Stripe URL here.
    STRIPE_PORTAL_RETURN_URL: str = "http://localhost:3000/billing"

    # Monetization prep: hardcoded on for every org today. The seam is here
    # (checked in the enrich/generate-message endpoints) so gating these by
    # an organization's actual plan later is a billing-lookup swap, not a
    # new code path.
    ENRICHMENT_ENABLED: bool = True
    AI_ENABLED: bool = True


settings = Settings()
