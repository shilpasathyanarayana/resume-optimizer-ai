from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432                  # ← changed from 3306
    DB_NAME: str = "resumeai"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    ADMIN_EMAILS: str = "" 
    # ── JWT ────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # ── App ────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    FRONTEND_ORIGIN: str = "http://localhost"

    # ── Groq ───────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Stripe ─────────────────────────────────────────────────────
    STRIPE_SECRET_KEY:           str = ""
    STRIPE_PUBLISHABLE_KEY:      str = ""
    STRIPE_WEBHOOK_SECRET:       str = ""
    STRIPE_PRICE_ID_PRO_MONTHLY: str = ""
    STRIPE_PRICE_ID_PRO_YEARLY:  str = ""
    STRIPE_PRICE_ID_PRO_MONTHLY_INR: str = ""
    STRIPE_PRICE_ID_PRO_YEARLY_INR:  str = ""

    @property
    def DATABASE_URL(self) -> str:                        # ← changed
         return (
        f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
        f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        f"?ssl=require"
    )

    @property
    def SYNC_DATABASE_URL(self) -> str:                   # ← new (for Alembic)
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()