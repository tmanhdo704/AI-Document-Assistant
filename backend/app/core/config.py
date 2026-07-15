from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DocAlly API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://app:app@localhost:5432/ai_document_assistant"
    )
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
