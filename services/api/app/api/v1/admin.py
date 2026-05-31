from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import Department, KnowledgeBase, QAAuditLog, Role, User
from app.schemas.admin import (
    PermissionMatrixDepartment,
    PermissionMatrixKnowledgeBase,
    PermissionMatrixResponse,
    PermissionMatrixRole,
    PermissionMatrixUser,
)
from app.schemas.qa import QAAuditRecordResponse
from app.services.permission_service import list_allowed_knowledge_bases


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


def _kb_scope(kb: KnowledgeBase) -> str:
    if kb.code == "public-policy" or kb.visibility == "public" or (kb.department and kb.department.code == "public"):
        return "public"
    if kb.code == "company-internal":
        return "company"
    return "department"


@router.get("/permission-matrix", response_model=PermissionMatrixResponse)
def get_permission_matrix(
    _: User = Depends(require_permission("admin:users:read")),
    db: Session = Depends(get_db),
) -> PermissionMatrixResponse:
    users = list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.email)).all())
    roles = list(db.scalars(select(Role).order_by(Role.name)).all())
    departments = list(db.scalars(select(Department).order_by(Department.code)).all())
    knowledge_bases = list(
        db.scalars(select(KnowledgeBase).where(KnowledgeBase.is_active.is_(True)).order_by(KnowledgeBase.code)).all()
    )

    matrix_users: list[PermissionMatrixUser] = []
    for user in users:
        allowed_kbs = list_allowed_knowledge_bases(db, user)
        matrix_users.append(
            PermissionMatrixUser(
                email=user.email,
                role=user.role.name if user.role else "",
                department=user.department.code if user.department else None,
                allowed_kb_codes=[item.code for item in allowed_kbs],
            )
        )

    return PermissionMatrixResponse(
        users=matrix_users,
        roles=[
            PermissionMatrixRole(
                name=item.name,
                description=item.description,
            )
            for item in roles
        ],
        departments=[
            PermissionMatrixDepartment(
                code=item.code,
                name=item.name,
            )
            for item in departments
        ],
        knowledge_bases=[
            PermissionMatrixKnowledgeBase(
                code=item.code,
                name=item.name,
                scope=_kb_scope(item),
            )
            for item in knowledge_bases
        ],
    )
