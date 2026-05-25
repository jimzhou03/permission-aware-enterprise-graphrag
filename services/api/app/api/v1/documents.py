from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.common import DocumentChunkPublic
from app.services.permission_service import list_allowed_knowledge_bases


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkPublic])
def list_document_chunks(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentChunkPublic]:
    try:
        document_uuid = UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc

    document = db.scalar(select(Document).where(Document.id == document_uuid))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    allowed_kb_ids = {kb.id for kb in list_allowed_knowledge_bases(db, current_user)}
    if document.knowledge_base_id not in allowed_kb_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this document")

    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == document.knowledge_base_id))
    kb_code = kb.code if kb else "unknown"

    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal.asc())
        ).all()
    )

    result: list[DocumentChunkPublic] = []
    for chunk in chunks:
        text = chunk.content.strip()
        preview = text.replace("\n", " ")
        if len(preview) > 220:
            preview = f"{preview[:220]}..."
        embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
        result.append(
            DocumentChunkPublic(
                id=chunk.id,
                document_id=chunk.document_id,
                knowledge_base_id=chunk.knowledge_base_id,
                knowledge_base_code=kb_code,
                chunk_index=chunk.ordinal,
                content_preview=preview,
                content=chunk.content,
                has_embedding=bool(embedding),
                embedding_dimension=len(embedding),
            )
        )
    return result
