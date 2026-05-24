from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.models import Document, DocumentChunk, KnowledgeBase
from app.services.embedding_service import embed_text
from app.services.entity_service import extract_entities


SAMPLE_DOCUMENT_MANIFEST: list[dict[str, Any]] = [
    {
        "kb_code": "public-general",
        "title": "Employee Handbook Summary",
        "path": ROOT_DIR / "sample_data" / "public" / "employee-handbook.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "hr-policy",
        "title": "Recruitment and Interview Policy",
        "path": ROOT_DIR / "sample_data" / "hr" / "recruitment-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "hr-policy",
        "title": "Leave and Attendance Policy",
        "path": ROOT_DIR / "sample_data" / "hr" / "leave-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "finance-policy",
        "title": "Compensation Confidentiality Policy",
        "path": ROOT_DIR / "sample_data" / "finance" / "compensation-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "finance-policy",
        "title": "Expense Reimbursement Standard",
        "path": ROOT_DIR / "sample_data" / "finance" / "reimbursement-policy.md",
        "source_label": "fictional-enterprise-doc",
    },
    {
        "kb_code": "tech-policy",
        "title": "Release and Incident Runbook",
        "path": ROOT_DIR / "sample_data" / "tech" / "release-runbook.md",
        "source_label": "fictional-enterprise-doc",
    },
]


def _split_into_chunks(text: str, max_chunk_size: int = 360) -> list[str]:
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


def _read_document(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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

    chunks = _split_into_chunks(content)
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
