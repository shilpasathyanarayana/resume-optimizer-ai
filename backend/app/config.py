from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "resumeai"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # ── JWT ────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-please"   # override via .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7       # 7 days

    # ── App ────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # ── Groq ──────────────────────────────────────────────────
    GROQ_API_KEY: str = ""   # ← "this field exists, default to empty if not in .env"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
