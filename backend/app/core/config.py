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

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    google_client_id: str

    guest_max_questions: int = 3
    guest_max_documents: int = 3
    user_max_documents: int = 10

    document_upload_directory: str = "storage/uploads"
    document_max_size_bytes: int = 25 * 1024 * 1024

    gemini_api_key: str = ""
    gemini_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta"
    )
    gemini_model: str = "gemini-2.5-pro"
    llm_timeout_seconds: float = 45.0
    llm_max_output_tokens: int = 800
    
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "document_chunks"

    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768
    embedding_batch_size: int = 32
    retrieval_top_k: int = 8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
