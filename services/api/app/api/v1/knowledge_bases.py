from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.common import KnowledgeBaseDocumentPublic, KnowledgeBasePublic
from app.services.permission_service import list_allowed_knowledge_bases


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def _infer_kb_language(kb: KnowledgeBase) -> str:
    if kb.code.startswith("cn-") or (kb.department and kb.department.code == "cn"):
        return "zh"
    if kb.code.startswith("en-") or (kb.department and kb.department.code == "en"):
        return "en"
    return "multi"


def _resolve_allowed_knowledge_base(
    db: Session,
    current_user: User,
    kb_identifier: str,
) -> KnowledgeBase:
    allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    for kb in allowed_kbs:
        if str(kb.id) == kb_identifier or kb.code == kb_identifier:
            return kb
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden to read this knowledge base",
    )


@router.get("", response_model=list[KnowledgeBasePublic])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeBasePublic]:
    knowledge_bases = list_allowed_knowledge_bases(db, current_user)
    return [
        KnowledgeBasePublic(
            id=kb.id,
            code=kb.code,
            display_name=kb.name,
            name=kb.name,
            language=_infer_kb_language(kb),
            description=kb.description,
            department=kb.department.code if kb.department else None,
            visibility=kb.visibility,
            version=kb.version,
        )
        for kb in knowledge_bases
    ]


@router.get("/{kb_id}/documents", response_model=list[KnowledgeBaseDocumentPublic])
def list_knowledge_base_documents(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeBaseDocumentPublic]:
    kb = _resolve_allowed_knowledge_base(db, current_user, kb_id)
    rows = db.execute(
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.knowledge_base_id == kb.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.title.asc())
    ).all()

    return [
        KnowledgeBaseDocumentPublic(
            id=document.id,
            knowledge_base_id=kb.id,
            knowledge_base_code=kb.code,
            title=document.title,
            source=document.source_label,
            created_at=document.created_at,
            chunk_count=int(chunk_count or 0),
        )
        for document, chunk_count in rows
    ]
