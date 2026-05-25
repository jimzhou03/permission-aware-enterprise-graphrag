from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR, get_settings
from app.models import Document, DocumentChunk, IngestionJob, KnowledgeBase, User
from app.services.embedding_service import embed_text
from app.services.entity_service import extract_entities
from app.services.graph_service import neo4j_service


settings = get_settings()

SUPPORTED_UPLOAD_SUFFIXES = {".md", ".txt"}
SUPPORTED_UPLOAD_MIME_TYPES = {
    "text/markdown",
    "text/plain",
    "text/x-markdown",
}


SAMPLE_DOCUMENT_MANIFEST: list[dict[str, Any]] = [
    {
        "kb_code": "cn-public",
        "title": "CN Public Policy Handbook",
        "path": ROOT_DIR / "sample_data" / "cn" / "cn-public-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "cn-internal",
        "title": "CN Internal Department Handbook",
        "path": ROOT_DIR / "sample_data" / "cn" / "cn-internal-handbook.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "en-public",
        "title": "EN Public Policy Handbook",
        "path": ROOT_DIR / "sample_data" / "en" / "en-public-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "en-internal",
        "title": "EN Internal Department Handbook",
        "path": ROOT_DIR / "sample_data" / "en" / "en-internal-handbook.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "public-policy",
        "title": "Public Visitor-safe Policy Handbook",
        "path": ROOT_DIR / "sample_data" / "public" / "public-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
]


@dataclass
class DocumentIngestionResult:
    document: Document
    chunk_count: int
    kb_version: int


def _split_seed_chunks(text: str, max_chunk_size: int = 360) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    paragraphs = [part.strip() for part in cleaned.split("\n\n") if part.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 1 <= max_chunk_size:
            buffer = f"{buffer}\n{paragraph}".strip()
            continue
        if buffer:
            chunks.append(buffer)
        if len(paragraph) <= max_chunk_size:
            buffer = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + max_chunk_size, len(paragraph))
            chunks.append(paragraph[start:end].strip())
            start = end
        buffer = ""

    if buffer:
        chunks.append(buffer)
    return chunks


def _normalize_text(raw_text: str) -> str:
    normalized = raw_text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    compact: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            compact.append(line)
            continue
        blank_count += 1
        if blank_count <= 2:
            compact.append("")
    return "\n".join(compact).strip()


def _split_semantic_units(text: str) -> list[str]:
    units: list[str] = []
    buffer: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            if buffer:
                units.append("\n".join(buffer).strip())
                buffer = []
            units.append(stripped)
            continue
        if not stripped:
            if buffer:
                units.append("\n".join(buffer).strip())
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        units.append("\n".join(buffer).strip())
    return [item for item in units if item]


def _split_long_unit(unit: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        return []
    step = max(chunk_size - max(overlap, 0), 1)
    parts: list[str] = []
    cursor = 0
    while cursor < len(unit):
        end = min(cursor + chunk_size, len(unit))
        chunk = unit[cursor:end].strip()
        if chunk:
            parts.append(chunk)
        if end >= len(unit):
            break
        cursor += step
    return parts


def split_text_for_ingestion(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    size = max(200, chunk_size or settings.upload_chunk_size_chars)
    overlap_size = min(max(0, overlap if overlap is not None else settings.upload_chunk_overlap_chars), size // 2)
    normalized = _normalize_text(text)
    if not normalized:
        return []

    units = _split_semantic_units(normalized)
    if not units:
        return []

    chunks: list[str] = []
    current = ""
    for unit in units:
        if len(unit) > size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_unit(unit, size, overlap_size))
            continue

        candidate = unit if not current else f"{current}\n\n{unit}"
        if len(candidate) <= size:
            current = candidate
            continue

        chunks.append(current.strip())
        overlap_prefix = current[-overlap_size:].strip() if overlap_size > 0 else ""
        current = f"{overlap_prefix}\n\n{unit}".strip() if overlap_prefix else unit
        if len(current) > size:
            long_parts = _split_long_unit(current, size, overlap_size)
            if not long_parts:
                current = ""
                continue
            chunks.extend(long_parts[:-1])
            current = long_parts[-1]

    if current:
        chunks.append(current.strip())
    return [item for item in chunks if item]


def _read_document(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _touch_kb_version(kb: KnowledgeBase) -> int:
    current = int(kb.version or 1)
    kb.version = current + 1
    return kb.version


def _create_ingestion_event(
    db: Session,
    *,
    action: str,
    status: str,
    actor: User | None,
    kb: KnowledgeBase | None,
    document: Document | None,
    filename: str,
    chunk_count: int,
    message: str,
    error_code: str | None = None,
) -> None:
    db.add(
        IngestionJob(
            document_id=document.id if document else None,
            status=status,
            message=message,
            stats={
                "action": action,
                "success": status == "success",
                "actor_user_id": str(actor.id) if actor else None,
                "actor_email": actor.email if actor else None,
                "knowledge_base_id": str(kb.id) if kb else None,
                "knowledge_base_code": kb.code if kb else None,
                "document_id": str(document.id) if document else None,
                "filename": filename,
                "chunk_count": chunk_count,
                "error_code": error_code,
            },
        )
    )


def record_ingestion_failure_event(
    db: Session,
    *,
    action: str,
    actor: User,
    kb: KnowledgeBase | None,
    document: Document | None,
    filename: str,
    error_code: str,
) -> None:
    try:
        _create_ingestion_event(
            db,
            action=action,
            status="failed",
            actor=actor,
            kb=kb,
            document=document,
            filename=filename,
            chunk_count=0,
            message=action,
            error_code=error_code,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def _upsert_document_and_chunks(
    db: Session,
    kb: KnowledgeBase,
    title: str,
    source_label: str,
    content: str,
) -> None:
    document = db.scalar(
        select(Document).where(
            Document.knowledge_base_id == kb.id,
            Document.title == title,
        )
    )
    if document is None:
        document = Document(
            knowledge_base_id=kb.id,
            title=title,
            source_label=source_label,
            version=1,
            status="active",
        )
        db.add(document)
        db.flush()

    chunks = _split_seed_chunks(content)
    if not chunks:
        return

    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    for idx, chunk in enumerate(chunks):
        entities = extract_entities(chunk)
        db.add(
            DocumentChunk(
                document_id=document.id,
                knowledge_base_id=kb.id,
                ordinal=idx,
                content=chunk,
                embedding=embed_text(chunk),
                chunk_metadata={"seeded": True, "source": source_label, "entities": entities},
            )
        )


def seed_documents_and_chunks(db: Session) -> None:
    kb_by_code = {
        kb.code: kb
        for kb in db.scalars(select(KnowledgeBase).where(KnowledgeBase.is_active.is_(True))).all()
    }
    for item in SAMPLE_DOCUMENT_MANIFEST:
        kb = kb_by_code.get(item["kb_code"])
        if kb is None:
            continue
        content = _read_document(item["path"])
        if not content.strip():
            continue
        _upsert_document_and_chunks(
            db=db,
            kb=kb,
            title=item["title"],
            source_label=item["source_label"],
            content=content,
        )
    db.commit()


def validate_upload_file(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    max_size_bytes: int | None = None,
) -> None:
    safe_filename = Path(filename).name
    suffix = Path(safe_filename).suffix.lower()
    normalized_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    size_limit = max_size_bytes or settings.upload_max_size_bytes

    if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
        raise ValueError("unsupported_file_extension")
    if normalized_content_type and normalized_content_type not in SUPPORTED_UPLOAD_MIME_TYPES:
        raise ValueError("unsupported_content_type")
    if size_bytes <= 0:
        raise ValueError("empty_file")
    if size_bytes > size_limit:
        raise ValueError("file_too_large")


def _sanitize_title(raw_title: str) -> str:
    compact = " ".join(raw_title.replace("_", " ").split()).strip()
    if not compact:
        return "uploaded-document"
    return compact[:255]


def _resolve_document_title(filename: str, title: str | None) -> str:
    if title and title.strip():
        return _sanitize_title(title)
    stem = Path(filename).stem
    return _sanitize_title(stem or "uploaded-document")


def _replace_document_chunks(
    db: Session,
    *,
    document: Document,
    kb: KnowledgeBase,
    normalized_text: str,
    source_filename: str,
    content_type: str,
    action: str,
) -> int:
    chunks = split_text_for_ingestion(normalized_text)
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    for index, chunk_text in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                knowledge_base_id=kb.id,
                ordinal=index,
                content=chunk_text,
                embedding=embed_text(chunk_text),
                chunk_metadata={
                    "source": source_filename,
                    "content_type": content_type,
                    "action": action,
                    "entities": extract_entities(chunk_text),
                },
            )
        )
    return len(chunks)


def upload_document_to_knowledge_base(
    db: Session,
    *,
    kb: KnowledgeBase,
    actor: User,
    filename: str,
    content_type: str,
    payload: bytes,
    title: str | None = None,
) -> DocumentIngestionResult:
    safe_filename = Path(filename).name
    text = payload.decode("utf-8")
    normalized_text = _normalize_text(text)
    if not normalized_text:
        raise ValueError("empty_file")

    document_title = _resolve_document_title(safe_filename, title)
    document = Document(
        knowledge_base_id=kb.id,
        title=document_title,
        source_label=f"upload:{safe_filename}"[:255],
        version=1,
        status="active",
    )
    db.add(document)
    db.flush()

    chunk_count = _replace_document_chunks(
        db,
        document=document,
        kb=kb,
        normalized_text=normalized_text,
        source_filename=safe_filename,
        content_type=content_type,
        action="document_upload",
    )
    document.version = 1
    kb_version = _touch_kb_version(kb)
    neo4j_service.mark_sync_needed(kb_id=kb.id, kb_code=kb.code)
    _create_ingestion_event(
        db,
        action="document_upload",
        status="success",
        actor=actor,
        kb=kb,
        document=document,
        filename=safe_filename,
        chunk_count=chunk_count,
        message="document_upload",
    )
    db.commit()
    db.refresh(document)
    return DocumentIngestionResult(document=document, chunk_count=chunk_count, kb_version=kb_version)


def reindex_document_chunks(
    db: Session,
    *,
    document: Document,
    kb: KnowledgeBase,
    actor: User,
) -> DocumentIngestionResult:
    existing_chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal.asc())
        ).all()
    )
    merged_text = "\n\n".join(item.content.strip() for item in existing_chunks if item.content.strip())
    normalized_text = _normalize_text(merged_text)
    if not normalized_text:
        raise ValueError("document_content_not_found")

    source_filename = document.source_label.replace("upload:", "", 1) if document.source_label else document.title
    chunk_count = _replace_document_chunks(
        db,
        document=document,
        kb=kb,
        normalized_text=normalized_text,
        source_filename=source_filename,
        content_type="text/markdown",
        action="document_reindex",
    )
    document.version = max(1, int(document.version or 1)) + 1
    kb_version = _touch_kb_version(kb)
    neo4j_service.mark_sync_needed(kb_id=kb.id, kb_code=kb.code)
    _create_ingestion_event(
        db,
        action="document_reindex",
        status="success",
        actor=actor,
        kb=kb,
        document=document,
        filename=source_filename,
        chunk_count=chunk_count,
        message="document_reindex",
    )
    db.commit()
    db.refresh(document)
    return DocumentIngestionResult(document=document, chunk_count=chunk_count, kb_version=kb_version)
