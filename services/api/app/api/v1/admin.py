from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import QAAuditLog, User
from app.schemas.qa import QAAuditRecordResponse


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=list[QAAuditRecordResponse])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> list[QAAuditRecordResponse]:
    rows = list(
        db.scalars(
            select(QAAuditLog).order_by(desc(QAAuditLog.created_at)).limit(limit)
        ).all()
    )
    return [
        QAAuditRecordResponse(
            request_id=row.request_id,
            user_id=row.user_id,
            question=row.question,
            answer=row.answer,
            denied=row.denied,
            refusal_reason=row.refusal_reason,
            hit_kb_ids=row.hit_kb_ids,
            hit_document_ids=row.hit_document_ids,
            hit_chunk_ids=row.hit_chunk_ids,
            mode=row.mode,
            model=row.model,
            cache_hit=row.cache_hit,
            latency_ms=row.latency_ms,
        )
        for row in rows
    ]

