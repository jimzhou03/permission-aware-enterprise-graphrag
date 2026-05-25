from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / ".env.example"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Permission-Aware Enterprise GraphRAG Assistant"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = Field(
        default="postgresql+psycopg://graphrag:graphrag@localhost:5432/graphrag"
    )
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "paegr"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password12345"

    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    embedding_dimensions: int = 64
    embedding_mode: Literal["mock", "local"] = "mock"
    local_embedding_backend: Literal["ollama", "sentence-transformers"] = Field(
        default="ollama",
        validation_alias=AliasChoices("LOCAL_EMBEDDING_BACKEND", "LOCAL_EMBEDDING_PROVIDER"),
    )
    local_embedding_model: str = Field(
        default="nomic-embed-text",
        validation_alias=AliasChoices("LOCAL_EMBEDDING_MODEL", "EMBEDDING_MODEL"),
    )
    local_embedding_base_url: str = Field(
        default="http://host.docker.internal:11434",
        validation_alias=AliasChoices("LOCAL_EMBEDDING_BASE_URL", "EMBEDDING_BASE_URL"),
    )
    local_embedding_timeout_seconds: float = Field(
        default=8.0,
        validation_alias=AliasChoices("LOCAL_EMBEDDING_TIMEOUT_SECONDS", "EMBEDDING_TIMEOUT_SECONDS"),
    )
    qa_top_k: int = 5
    enable_pgvector_sql_retrieval: bool = True
    cache_ttl_seconds: int = 1200
    cache_refusal_ttl_seconds: int = 300
    upload_max_size_bytes: int = 1_048_576
    upload_chunk_size_chars: int = 1000
    upload_chunk_overlap_chars: int = 150
    prompt_version: str = "mvp-2026-05"
    permission_policy_version: str = "rbac-v1"

    llm_mode: Literal["mock", "ollama", "openai-compatible", "api"] = "mock"
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 30.0
    llm_ollama_base_url: str = Field(
        default="http://host.docker.internal:11434",
        validation_alias=AliasChoices("LLM_OLLAMA_BASE_URL", "OLLAMA_LLM_BASE_URL"),
    )
    llm_ollama_model: str = Field(
        default="qwen2.5:7b-instruct",
        validation_alias=AliasChoices("LLM_OLLAMA_MODEL", "OLLAMA_LLM_MODEL"),
    )
    llm_ollama_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("LLM_OLLAMA_TIMEOUT_SECONDS", "OLLAMA_LLM_TIMEOUT_SECONDS"),
    )

    local_router_mode: Literal["rules", "ollama"] = "rules"
    ollama_base_url: str = Field(
        default="http://host.docker.internal:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "LOCAL_ROUTER_BASE_URL"),
    )
    ollama_router_model: str = Field(
        default="qwen2.5:0.5b-instruct",
        validation_alias=AliasChoices("OLLAMA_ROUTER_MODEL", "LOCAL_ROUTER_MODEL"),
    )
    ollama_router_timeout_seconds: float = Field(
        default=8.0,
        validation_alias=AliasChoices("OLLAMA_ROUTER_TIMEOUT_SECONDS", "LOCAL_ROUTER_TIMEOUT_SECONDS"),
    )

    seed_on_startup: bool = True
    sync_neo4j_on_startup: bool = False
    uvicorn_reload: bool = True

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
