from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.qa import GraphPath


GraphNodeType = Literal["knowledge_base", "document", "chunk", "entity", "department", "topic"]
GraphEdgeType = Literal[
    "CONTAINS",
    "HAS_CHUNK",
    "MENTIONS",
    "BELONGS_TO",
    "RELATED_TO",
    "DERIVED_FROM",
    "DOCUMENT_MENTIONS_ENTITY",
    "DEPARTMENT_OWNS_DOCUMENT",
    "ROLE_CAN_ACCESS_KB",
    "REQUEST_RETRIEVED_CHUNK",
]


class GraphNodePublic(BaseModel):
    id: str
    label: str
    type: GraphNodeType
    kb_id: str | None = None
    kb_code: str | None = None
    title: str | None = None
    metadata_summary: str | None = None
    entity_type: str | None = None
    canonical_name: str | None = None
    source_document_id: str | None = None
    confidence: float | None = None
    evidence_text: str | None = None


class GraphEdgePublic(BaseModel):
    id: str
    source: str
    target: str
    type: GraphEdgeType
    label: str
    relation_type: str | None = None


class GraphStatusResponse(BaseModel):
    neo4j_configured: bool
    neo4j_available: bool
    graph_sync_enabled: bool
    graph_sync_needed: bool
    pending_sync_kb_codes: list[str] = Field(default_factory=list)
    node_count: int | None = None
    relationship_count: int | None = None
    fallback_mode: str
    last_sync_summary: dict[str, str | int | bool | None] = Field(default_factory=dict)


class GraphOverviewResponse(BaseModel):
    allowed_kb_ids: list[str] = Field(default_factory=list)
    allowed_kb_codes: list[str] = Field(default_factory=list)
    nodes: list[GraphNodePublic] = Field(default_factory=list)
    edges: list[GraphEdgePublic] = Field(default_factory=list)
    fallback_used: bool = False
    generated_at: datetime
    security_notes: list[str] = Field(default_factory=list)


class GraphSyncResponse(BaseModel):
    status: str
    fallback_used: bool
    summary: dict[str, str | int | bool | None] = Field(default_factory=dict)


class QAGraphResponse(BaseModel):
    request_id: str
    mode: str
    viewer_email: str | None = None
    viewer_role: str | None = None
    viewer_department: str | None = None
    allowed_kb_ids: list[str] = Field(default_factory=list)
    allowed_kb_codes: list[str] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    nodes: list[GraphNodePublic] = Field(default_factory=list)
    edges: list[GraphEdgePublic] = Field(default_factory=list)
    fallback_used: bool = False
    security_notes: list[str] = Field(default_factory=list)
