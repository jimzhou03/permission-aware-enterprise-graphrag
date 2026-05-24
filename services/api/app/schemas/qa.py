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
    citations: list[Citation] = []
    graph_paths: list[GraphPath] = []

