from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DocumentChunk, KnowledgeBase
from app.services.embedding_service import cosine_similarity, embed_text


settings = get_settings()


@dataclass
class RetrievedChunk:
    kb_id: UUID
    kb_code: str
    kb_name: str
    document_id: UUID
    document_title: str
    chunk_id: UUID
    score: float
    content: str


def _to_uuid_set(values: Iterable[UUID]) -> set[UUID]:
    return {value for value in values}


def retrieve_permission_scoped_chunks(
    db: Session,
    question: str,
    allowed_kb_ids: list[UUID],
    scoped_kb_codes: list[str],
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    if not allowed_kb_ids:
        return []

    limit = top_k or settings.qa_top_k
    allowed_set = _to_uuid_set(allowed_kb_ids)
    question_vec = embed_text(question)

    kb_statement = select(KnowledgeBase).where(KnowledgeBase.id.in_(list(allowed_set)))
    if scoped_kb_codes:
        kb_statement = kb_statement.where(KnowledgeBase.code.in_(scoped_kb_codes))
    kbs = list(db.scalars(kb_statement).all())
    kb_by_id = {kb.id: kb for kb in kbs}
    selected_ids = set(kb_by_id.keys())
    if not selected_ids:
        return []

    # Critical security property: chunk query is pre-filtered by allowed kb ids.
    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.knowledge_base_id.in_(list(selected_ids)))
        .order_by(DocumentChunk.ordinal.asc())
    )
    chunks = list(db.scalars(statement).all())
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        kb = kb_by_id.get(chunk.knowledge_base_id)
        if kb is None or chunk.document is None:
            continue
        embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
        score = cosine_similarity(question_vec, embedding)
        scored.append(
            RetrievedChunk(
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=chunk.document.id,
                document_title=chunk.document.title,
                chunk_id=chunk.id,
                score=score,
                content=chunk.content,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]

