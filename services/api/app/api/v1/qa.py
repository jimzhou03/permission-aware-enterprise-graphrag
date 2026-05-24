from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models import User
from app.schemas.qa import AskRequest, AskResponse, QAAuditRecordResponse
from app.services.audit_service import get_qa_audit_by_request_id
from app.services.auth_service import user_has_permission
from app.services.qa_service import ask_question


router = APIRouter(prefix="/qa", tags=["qa"])


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

