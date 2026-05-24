from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QAAuditLog


def create_qa_audit_log(
    db: Session,
    request_id: str,
    user_id: UUID | None,
    question: str,
    answer: str,
    denied: bool,
    refusal_reason: str,
    hit_kb_ids: list[str],
    hit_document_ids: list[str],
    hit_chunk_ids: list[str],
    mode: str,
    model: str,
    latency_ms: int,
    cache_hit: bool = False,
) -> QAAuditLog:
    entry = QAAuditLog(
        request_id=request_id,
        user_id=user_id,
        question=question,
        answer=answer,
        denied=denied,
        refusal_reason=refusal_reason,
        hit_kb_ids=hit_kb_ids,
        hit_document_ids=hit_document_ids,
        hit_chunk_ids=hit_chunk_ids,
        cache_hit=cache_hit,
        mode=mode,
        model=model,
        latency_ms=latency_ms,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_qa_audit_by_request_id(db: Session, request_id: str) -> QAAuditLog | None:
    return db.scalar(select(QAAuditLog).where(QAAuditLog.request_id == request_id))
