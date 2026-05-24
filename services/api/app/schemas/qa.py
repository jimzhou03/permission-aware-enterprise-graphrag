from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


AskMode = Literal["auto", "rag", "graphrag"]


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    mode: AskMode = "auto"
    knowledge_base_codes: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    target_department: str | None
    mode: Literal["direct", "rag", "graphrag"]
    requires_rag: bool
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
    mode: Literal["direct", "rag", "graphrag"]
    route: RouteDecision
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
