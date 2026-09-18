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

    # AI case assistant (ask/summary/legal-section-suggestion features).
    # Both providers can be configured; OpenAI is used if its key is set,
    # otherwise Anthropic, otherwise the feature returns a clear "not
    # configured" error naming OPENAI_API_KEY - see _default_llm_client in
    # app/services/assistant.py.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    # Override for OpenAI-COMPATIBLE providers (Groq, OpenRouter, a local
    # vLLM/Ollama server, etc.) that use OpenAI's request format at their
    # own URL - e.g. Groq: https://api.groq.com/openai/v1,
    # OpenRouter: https://openrouter.ai/api/v1. Leave as-is for real OpenAI.
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # Object/scene detection for image and video evidence (self-hosted,
    # no per-call cost - see requirements-vision.txt). Off by default: the
    # dependency (ultralytics/torch) is heavy and this needs meaningfully
    # more CPU/RAM than the base app, not something to silently turn on.
    enable_vision_analysis: bool = False
    vision_model_path: str = "yolov8n.pt"
    vision_max_video_frames: int = 10
    vision_frame_interval_seconds: float = 2.0
    vision_confidence_threshold: float = 0.35

    # Blockchain anchoring: periodically commits the audit chain's current
    # head (sequence + entry_hash) to a public blockchain by sending a
    # zero-value transaction to a wallet the backend controls, with the
    # anchor payload in the transaction's data field - no smart contract
    # needed, the calldata itself is the permanent public record. This is
    # what turns "hash-chained log in our own Postgres" into "independently
    # verifiable even if someone with service_role DB access rewrote our
    # history" - see app/services/blockchain_anchor.py for the honest
    # explanation of exactly what this does and doesn't guarantee. Off by
    # default: it needs a funded testnet wallet, not something to silently
    # turn on.
    enable_blockchain_anchor: bool = False
    blockchain_rpc_url: str | None = None
    blockchain_private_key: str | None = None
    blockchain_chain_id: int = 80002  # Polygon Amoy testnet
    blockchain_network_name: str = "Polygon Amoy Testnet"
    blockchain_explorer_tx_base_url: str = "https://amoy.polygonscan.com/tx/"
    # Defaults to anchoring to the sender's own address (a plain self-transfer
    # carrying data) - set only if you want a distinct, dedicated anchor address.
    blockchain_anchor_to_address: str | None = None
    blockchain_gas_limit: int = 100_000
    blockchain_confirmation_timeout_seconds: float = 60.0

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