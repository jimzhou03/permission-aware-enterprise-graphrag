from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.qa import (
    AskRequest,
    AskResponse,
    QAAuditRecordResponse,
    QATraceResponse,
    TraceRetrievedChunk,
)
from app.services.audit_service import get_qa_audit_by_request_id
from app.services.auth_service import user_has_permission
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.qa_service import ask_question
from app.services.rag_service import get_retrieval_runtime


router = APIRouter(prefix="/qa", tags=["qa"])


def _parse_uuid_list(values: list[str]) -> list[UUID]:
    parsed: list[UUID] = []
    for value in values:
        try:
            parsed.append(UUID(value))
        except ValueError:
            continue
    return parsed


def _parse_retrieval_engine_from_model(model: str) -> str | None:
    marker = "|retrieval="
    if marker not in model:
        return None
    return model.split(marker, maxsplit=1)[1].strip() or None


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(require_permission("qa:ask")),
    db: Session = Depends(get_db),
) -> AskResponse:
    result = ask_question(db=db, user=current_user, payload=payload)
    return result.response


@router.get("/{request_id}", response_model=QAAuditRecordResponse)
def get_request_detail(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QAAuditRecordResponse:
    record = get_qa_audit_by_request_id(db, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request record not found")

    is_owner = record.user_id is not None and record.user_id == current_user.id
    can_read_audit = user_has_permission(db, current_user, "audit:read")
    if not is_owner and not can_read_audit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this record")

    return QAAuditRecordResponse(
        request_id=record.request_id,
        user_id=record.user_id,
        question=record.question,
        answer=record.answer,
        denied=record.denied,
        refusal_reason=record.refusal_reason,
        hit_kb_ids=record.hit_kb_ids,
        hit_document_ids=record.hit_document_ids,
        hit_chunk_ids=record.hit_chunk_ids,
        mode=record.mode,
        model=record.model,
        cache_hit=record.cache_hit,
        latency_ms=record.latency_ms,
    )


@router.get("/{request_id}/trace", response_model=QATraceResponse)
def get_request_trace(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QATraceResponse:
    record = get_qa_audit_by_request_id(db, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request record not found")

    is_owner = record.user_id is not None and record.user_id == current_user.id
    can_read_audit = user_has_permission(db, current_user, "audit:read")
    if not is_owner and not can_read_audit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this trace")

    viewer_allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    viewer_allowed_kb_ids = {kb.id for kb in viewer_allowed_kbs}

    request_user = record.user
    request_allowed_kbs = list_allowed_knowledge_bases(db, request_user) if request_user else []
    allowed_kb_ids = [str(kb.id) for kb in request_allowed_kbs]
    allowed_kb_codes = [kb.code for kb in request_allowed_kbs]
    current_runtime = get_retrieval_runtime(db)

    hit_kb_ids = record.hit_kb_ids if isinstance(record.hit_kb_ids, list) else []
    hit_document_ids = record.hit_document_ids if isinstance(record.hit_document_ids, list) else []
    hit_chunk_ids = record.hit_chunk_ids if isinstance(record.hit_chunk_ids, list) else []

    hit_chunk_uuid_list = _parse_uuid_list(hit_chunk_ids)
    chunk_rows = db.execute(
        select(DocumentChunk, Document, KnowledgeBase)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(KnowledgeBase, KnowledgeBase.id == DocumentChunk.knowledge_base_id)
        .where(DocumentChunk.id.in_(hit_chunk_uuid_list))
    ).all()
    row_by_chunk_id = {str(chunk.id): (chunk, document, kb) for chunk, document, kb in chunk_rows}

    reconstructed_chunks: list[TraceRetrievedChunk] = []
    omitted_for_scope = 0
    for chunk_id in hit_chunk_ids:
        row = row_by_chunk_id.get(chunk_id)
        if row is None:
            continue
        chunk, document, kb = row
        if kb.id not in viewer_allowed_kb_ids:
            omitted_for_scope += 1
            continue
        embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
        preview = chunk.content.strip().replace("\n", " ")
        if len(preview) > 220:
            preview = f"{preview[:220]}..."
        reconstructed_chunks.append(
            TraceRetrievedChunk(
                chunk_id=chunk.id,
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=document.id,
                document_title=document.title,
                chunk_index=chunk.ordinal,
                content_preview=preview,
                content=chunk.content,
                has_embedding=bool(embedding),
                embedding_dimension=len(embedding),
            )
        )

    trace_limits = [
        "retrieved_chunks are reconstructed from current document_chunks using hit_chunk_ids; historical full snapshots are not persisted in qa_audit_logs.",
        "allowed_kb_ids are reconstructed from current ACL scope and may differ from historical scope at request time.",
    ]
    if omitted_for_scope > 0:
        trace_limits.append(
            f"{omitted_for_scope} chunk(s) were omitted because current viewer scope does not allow their knowledge base."
        )
    if hit_chunk_ids and not reconstructed_chunks:
        trace_limits.append(
            "No authorized chunk content is available to current viewer; trace falls back to identifier-level metadata."
        )

    return QATraceResponse(
        request_id=record.request_id,
        user_id=record.user_id,
        user_email=request_user.email if request_user else None,
        role=request_user.role.name if request_user and request_user.role else None,
        department=request_user.department.code if request_user and request_user.department else None,
        question=record.question,
        answer=record.answer,
        mode=record.mode,
        denied=record.denied,
        refusal_reason=record.refusal_reason,
        allowed_kb_ids=allowed_kb_ids,
        allowed_kb_codes=allowed_kb_codes,
        hit_kb_ids=hit_kb_ids,
        hit_document_ids=hit_document_ids,
        hit_chunk_ids=hit_chunk_ids,
        retrieved_chunks=reconstructed_chunks,
        retrieval_engine=(
            _parse_retrieval_engine_from_model(record.model) or current_runtime.retrieval_engine
        ),
        cache_hit=record.cache_hit,
        model=record.model,
        latency_ms=record.latency_ms,
        trace_limits=trace_limits,
    )
