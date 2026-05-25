from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: UUID
    email: str
    full_name: str
    role: str
    department: str | None
    permissions: list[str] = Field(default_factory=list)


class KnowledgeBasePublic(ORMModel):
    id: UUID
    code: str
    display_name: str
    name: str
    language: str
    description: str
    department: str | None
    visibility: str
    version: int


class KnowledgeBaseDocumentPublic(ORMModel):
    id: UUID
    knowledge_base_id: UUID
    knowledge_base_code: str
    title: str
    source: str
    created_at: datetime
    chunk_count: int


class DocumentChunkPublic(ORMModel):
    id: UUID
    document_id: UUID
    knowledge_base_id: UUID
    knowledge_base_code: str
    chunk_index: int
    content_preview: str
    content: str
    has_embedding: bool
    embedding_dimension: int


class RetrievalConfigPublic(BaseModel):
    embedding_provider: str
    embedding_dimension: int
    retrieval_engine: str
    top_k: int
    default_top_k: int
    generator_mode: str
    router_mode: str
    router_model: str
    router_availability: str
    router_fallback_last: bool
    router_error_last: str | None = None
    pgvector_available: bool
    sql_vector_search_enabled: bool
    pgvector_sql_retrieval_enabled: bool
    pgvector_field_available: bool
    cache_backend: str
    model_mode: str
    function_calling_mode: str
    llm_autonomous_tool_calling: bool
    permission_authority: str


class AuditLogPublic(ORMModel):
    id: UUID
    request_id: str
    user_id: UUID | None
    question: str
    answer: str
    denied: bool
    refusal_reason: str
    hit_kb_ids: list[str]
    hit_document_ids: list[str]
    hit_chunk_ids: list[str]
    cache_hit: bool
    mode: str
    model: str
    latency_ms: int
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
