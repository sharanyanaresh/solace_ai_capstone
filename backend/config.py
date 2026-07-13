"""Application settings, loaded from environment (and a local .env in dev)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = .../backend/app/config.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # database
    database_url: str = "sqlite:///./solace_dev.db"

    # auth
    jwt_secret: str = "dev-insecure-change-me"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 7
    allow_open_registration: bool = True

    # llm (groq) — primary + optional fallback key for failover
    groq_api_key: str | None = None
    groq_api_key_fallback: str | None = None
    groq_model_small: str = "llama-3.1-8b-instant"
    groq_model_large: str = "llama-3.3-70b-versatile"
    groq_max_retries: int = 3

    # pubmed / ncbi
    ncbi_email: str = "solace@example.com"
    ncbi_api_key: str | None = None
    pubmed_retmax: int = 30            # abstracts fetched from PubMed per search

    # pipeline depth (tunable — higher = deeper research, longer answers, more tokens/latency)
    pipeline_multi_query: bool = True  # retrieve per sub-question, not just the main query
    pipeline_subquery_retmax: int = 15 # abstracts per sub-question search
    pipeline_top_k: int = 12           # passages kept after BM25 ranking
    factcheck_passages: int = 12       # passages shown to the fact-checker
    factcheck_abstract_chars: int = 1400  # per-abstract chars (near-full abstracts)
    factcheck_max_tokens: int = 3500
    synth_max_tokens: int = 4000
    graph_max_relations: int = 12

    # misc
    cors_origins: str = "*"

    @property
    def sqlalchemy_url(self) -> str:
        """Normalize Render's postgres:// URL to a SQLAlchemy-friendly driver URL."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
