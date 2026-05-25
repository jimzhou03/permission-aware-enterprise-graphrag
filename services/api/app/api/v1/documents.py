from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.common import DocumentChunkPublic, DocumentIngestionResponse
from app.services.ingestion_service import record_ingestion_failure_event, reindex_document_chunks
from app.services.permission_service import can_write_knowledge_base, list_allowed_knowledge_bases


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


@router.post("/{document_id}/reindex", response_model=DocumentIngestionResponse)
def reindex_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentIngestionResponse:
    try:
        document_uuid = UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc

    document = db.scalar(select(Document).where(Document.id == document_uuid))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.id == document.knowledge_base_id))
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    allowed_kb_ids = {item.id for item in list_allowed_knowledge_bases(db, current_user)}
    if kb.id not in allowed_kb_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this document")
    if not can_write_knowledge_base(db, current_user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to reindex this document")

    try:
        result = reindex_document_chunks(db=db, document=document, kb=kb, actor=current_user)
    except ValueError as exc:
        db.rollback()
        reason = str(exc)
        record_ingestion_failure_event(
            db,
            action="document_reindex",
            actor=current_user,
            kb=kb,
            document=document,
            filename=document.source_label,
            error_code=reason,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        record_ingestion_failure_event(
            db,
            action="document_reindex",
            actor=current_user,
            kb=kb,
            document=document,
            filename=document.source_label,
            error_code="reindex_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="reindex_error") from exc

    filename = document.source_label.replace("upload:", "", 1) if document.source_label else document.title
    return DocumentIngestionResponse(
        action="document_reindex",
        status="success",
        knowledge_base_id=kb.id,
        knowledge_base_code=kb.code,
        knowledge_base_version=result.kb_version,
        document_id=document.id,
        document_title=document.title,
        document_source=document.source_label,
        document_version=document.version,
        filename=filename,
        chunk_count=result.chunk_count,
    )
