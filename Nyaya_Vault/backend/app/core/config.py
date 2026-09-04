from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


CsvList = Annotated[list[str], BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CaseVault API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    expose_docs: bool = True

    supabase_url: str = Field(default="http://127.0.0.1:54321")
    # Preferred 2026 Supabase keys. Legacy anon/service_role names remain
    # supported so existing deployments can migrate without downtime.
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    storage_bucket: str = "case-documents"

    cors_origins: CsvList = ["http://localhost:5173", "http://127.0.0.1:5173"]
    request_timeout_seconds: float = 30.0
    processing_timeout_seconds: float = 180.0
    processing_lease_seconds: int = 300
    max_upload_bytes: int = 25 * 1024 * 1024
    auto_process_uploads: bool = False

    enable_semantic_embeddings: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_chunk_chars: int = 1200
    embedding_chunk_overlap: int = 180

    max_ocr_pages: int = 25
    poppler_path: str | None = None
    tesseract_cmd: str | None = None
    temp_dir: Path = Path("./.tmp")

    @property
    def normalized_supabase_url(self) -> str:
        return self.supabase_url.rstrip("/")

    @property
    def browser_api_key(self) -> str:
        return self.supabase_publishable_key or self.supabase_anon_key or "dev-publishable-key"

    @property
    def backend_api_key(self) -> str:
        return self.supabase_secret_key or self.supabase_service_role_key or "dev-secret-key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
