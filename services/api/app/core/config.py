from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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
    qa_top_k: int = 5
    cache_ttl_seconds: int = 1200
    cache_refusal_ttl_seconds: int = 300
    prompt_version: str = "mvp-2026-05"
    permission_policy_version: str = "rbac-v1"

    llm_mode: Literal["mock", "api"] = "mock"
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    local_router_mode: Literal["rules", "ollama"] = "rules"
    local_router_base_url: str = "http://localhost:11434/v1"
    local_router_api_key: str = "ollama"
    local_router_model: str = "qwen2.5:0.5b-instruct"

    seed_on_startup: bool = True
    sync_neo4j_on_startup: bool = False

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

