from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


AskMode = Literal["auto", "rag", "graphrag"]
ResponseMode = Literal["direct", "rag", "graphrag", "general"]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    mode: AskMode = "auto"
    knowledge_base_codes: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    target_department: str | None
    mode: ResponseMode
    requires_rag: bool
    need_rag: bool = False
    confidence: float
    reason: str


class Citation(BaseModel):
    kb_id: UUID
    kb_code: str
    kb_name: str
    document_id: UUID
    document_title: str
    chunk_id: UUID
    score: float
    excerpt: str


class GraphPath(BaseModel):
    chunk_id: UUID
    path: list[str]
    explanation: str


class AskResponse(BaseModel):
    request_id: str
    answer: str
    denied: bool
    refusal_reason: str | None = None
    cache_hit: bool
    mode: ResponseMode
    route: RouteDecision
    retrieved_chunks: list[Citation] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)


class QAAuditRecordResponse(BaseModel):
    request_id: str
    user_id: UUID | None
    question: str
    answer: str
    denied: bool
    refusal_reason: str
    hit_kb_ids: list[str] = Field(default_factory=list)
    hit_document_ids: list[str] = Field(default_factory=list)
    hit_chunk_ids: list[str] = Field(default_factory=list)
    mode: str
    model: str
    cache_hit: bool
    latency_ms: int


class TraceRetrievedChunk(BaseModel):
    chunk_id: UUID
    kb_id: UUID
    kb_code: str
    kb_name: str
    document_id: UUID
    document_title: str
    chunk_index: int
    content_preview: str
    content: str
    has_embedding: bool
    embedding_dimension: int


class QATraceResponse(BaseModel):
    request_id: str
    user_id: UUID | None
    user_email: str | None = None
    role: str | None = None
    department: str | None = None
    question: str
    answer: str
    mode: str
    denied: bool
    refusal_reason: str
    allowed_kb_ids: list[str] = Field(default_factory=list)
    allowed_kb_codes: list[str] = Field(default_factory=list)
    hit_kb_ids: list[str] = Field(default_factory=list)
    hit_document_ids: list[str] = Field(default_factory=list)
    hit_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunks: list[TraceRetrievedChunk] = Field(default_factory=list)
    retrieval_engine: str
    cache_hit: bool
    model: str
    latency_ms: int
    trace_limits: list[str] = Field(default_factory=list)
