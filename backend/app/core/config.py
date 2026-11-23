from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    APP_ENV: str = "development"

    # Comma-separated list of browser origins allowed to call the API.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Optional language-model classifier. Disabled by default so that no
    # business-related text leaves the server unless explicitly approved.
    ASSISTANT_LLM_ENABLED: bool = False
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_TIMEOUT_SECONDS: float = Field(default=8.0, gt=0, le=60)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
