from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.common import DocumentIngestionResponse, KnowledgeBaseDocumentPublic, KnowledgeBasePublic
from app.services.ingestion_service import (
    record_ingestion_failure_event,
    upload_document_to_knowledge_base,
    validate_upload_file,
)
from app.services.permission_service import can_write_knowledge_base, list_allowed_knowledge_bases


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
settings = get_settings()


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


@router.post("/{kb_id}/documents/upload", response_model=DocumentIngestionResponse)
async def upload_knowledge_base_document(
    kb_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentIngestionResponse:
    kb = _resolve_allowed_knowledge_base(db, current_user, kb_id)
    if not can_write_knowledge_base(db, current_user, kb):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to upload to this knowledge base")

    safe_filename = (file.filename or "").strip()
    if not safe_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing upload filename")

    payload = await file.read(settings.upload_max_size_bytes + 1)
    content_type = file.content_type or ""
    try:
        validate_upload_file(
            filename=safe_filename,
            content_type=content_type,
            size_bytes=len(payload),
            max_size_bytes=settings.upload_max_size_bytes,
        )
    except ValueError as exc:
        reason = str(exc)
        if reason == "file_too_large":
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=reason) from exc
        if reason in {"unsupported_file_extension", "unsupported_content_type"}:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=reason) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason) from exc

    try:
        result = upload_document_to_knowledge_base(
            db=db,
            kb=kb,
            actor=current_user,
            filename=safe_filename,
            content_type=content_type,
            payload=payload,
            title=title,
        )
    except UnicodeDecodeError as exc:
        db.rollback()
        record_ingestion_failure_event(
            db,
            action="document_upload",
            actor=current_user,
            kb=kb,
            document=None,
            filename=safe_filename,
            error_code="invalid_utf8",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_utf8") from exc
    except ValueError as exc:
        db.rollback()
        reason = str(exc)
        record_ingestion_failure_event(
            db,
            action="document_upload",
            actor=current_user,
            kb=kb,
            document=None,
            filename=safe_filename,
            error_code=reason,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        record_ingestion_failure_event(
            db,
            action="document_upload",
            actor=current_user,
            kb=kb,
            document=None,
            filename=safe_filename,
            error_code="upload_indexing_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_indexing_error") from exc

    return DocumentIngestionResponse(
        action="document_upload",
        status="success",
        knowledge_base_id=kb.id,
        knowledge_base_code=kb.code,
        knowledge_base_version=result.kb_version,
        document_id=result.document.id,
        document_title=result.document.title,
        document_source=result.document.source_label,
        document_version=result.document.version,
        filename=safe_filename,
        chunk_count=result.chunk_count,
    )
