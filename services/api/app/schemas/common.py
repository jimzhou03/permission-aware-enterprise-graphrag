from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: UUID
    email: str
    full_name: str
    role: str
    department: str | None
    permissions: list[str] = []


class KnowledgeBasePublic(ORMModel):
    id: UUID
    code: str
    name: str
    description: str
    department: str | None
    visibility: str
    version: int


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
    detail: dict[str, Any] = {}

