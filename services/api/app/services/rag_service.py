from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, cast, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.models import DocumentChunk, KnowledgeBase
from app.services.embedding_service import cosine_similarity, embed_text


settings = get_settings()


RETRIEVAL_ENGINE_PGVECTOR_SQL = "pgvector_sql"
RETRIEVAL_ENGINE_PYTHON_FALLBACK = "python_cosine_fallback"


@dataclass
class RetrievedChunk:
    kb_id: UUID
    kb_code: str
    kb_name: str
    document_id: UUID
    document_title: str
    chunk_id: UUID
    score: float
    content: str


@dataclass
class RetrievalRuntime:
    retrieval_engine: str
    pgvector_available: bool
    sql_vector_search_enabled: bool
    backend_name: str
    fallback_reason: str | None = None

    @property
    def cache_token(self) -> str:
        return f"{self.retrieval_engine}:{self.backend_name}:{int(self.sql_vector_search_enabled)}"


def _to_uuid_set(values: Iterable[UUID]) -> set[UUID]:
    return {value for value in values}


def _is_postgresql(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind and bind.dialect.name == "postgresql")


def _probe_pgvector_available(db: Session) -> bool:
    if not _is_postgresql(db):
        return False
    try:
        result = db.scalar(text("SELECT 1 FROM pg_extension WHERE extname='vector' LIMIT 1"))
    except SQLAlchemyError:
        return False
    return result == 1


def get_retrieval_runtime(db: Session) -> RetrievalRuntime:
    bind = db.get_bind()
    backend_name = bind.dialect.name if bind else "unknown"
    pgvector_available = _probe_pgvector_available(db)
    sql_vector_search_enabled = bool(
        getattr(settings, "enable_pgvector_sql_retrieval", True)
        and backend_name == "postgresql"
        and pgvector_available
    )
    if sql_vector_search_enabled:
        return RetrievalRuntime(
            retrieval_engine=RETRIEVAL_ENGINE_PGVECTOR_SQL,
            pgvector_available=pgvector_available,
            sql_vector_search_enabled=True,
            backend_name=backend_name,
        )

    fallback_reason = "pgvector_sql_disabled"
    if backend_name != "postgresql":
        fallback_reason = "non_postgresql_backend"
    elif not pgvector_available:
        fallback_reason = "pgvector_extension_unavailable"
    return RetrievalRuntime(
        retrieval_engine=RETRIEVAL_ENGINE_PYTHON_FALLBACK,
        pgvector_available=pgvector_available,
        sql_vector_search_enabled=False,
        backend_name=backend_name,
        fallback_reason=fallback_reason,
    )


def _retrieve_with_python_cosine_fallback(
    db: Session,
    question: str,
    kb_by_id: dict[UUID, KnowledgeBase],
    selected_ids: set[UUID],
    limit: int,
) -> list[RetrievedChunk]:
    question_vec = embed_text(question)
    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.knowledge_base_id.in_(list(selected_ids)))
        .order_by(DocumentChunk.ordinal.asc())
    )
    chunks = list(db.scalars(statement).all())
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        kb = kb_by_id.get(chunk.knowledge_base_id)
        if kb is None or chunk.document is None:
            continue
        embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
        score = cosine_similarity(question_vec, embedding)
        scored.append(
            RetrievedChunk(
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=chunk.document.id,
                document_title=chunk.document.title,
                chunk_id=chunk.id,
                score=score,
                content=chunk.content,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]


def _retrieve_with_pgvector_sql(
    db: Session,
    question: str,
    kb_by_id: dict[UUID, KnowledgeBase],
    selected_ids: set[UUID],
    limit: int,
) -> list[RetrievedChunk]:
    question_vec = embed_text(question)
    vector_type = Vector(settings.embedding_dimensions)
    raw_distance = cast(DocumentChunk.embedding, vector_type).op("<=>")(cast(question_vec, vector_type))
    distance_expr = cast(raw_distance, Float)
    statement = (
        select(DocumentChunk, distance_expr.label("distance"))
        .where(DocumentChunk.knowledge_base_id.in_(list(selected_ids)))
        .order_by(distance_expr.asc(), DocumentChunk.ordinal.asc())
        .limit(limit)
    )
    rows = db.execute(statement).all()
    scored: list[RetrievedChunk] = []
    for chunk, distance in rows:
        kb = kb_by_id.get(chunk.knowledge_base_id)
        if kb is None or chunk.document is None:
            continue
        distance_value = float(distance or 1.0)
        score = max(0.0, 1.0 - distance_value)
        scored.append(
            RetrievedChunk(
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=chunk.document.id,
                document_title=chunk.document.title,
                chunk_id=chunk.id,
                score=score,
                content=chunk.content,
            )
        )
    return scored


def retrieve_permission_scoped_chunks(
    db: Session,
    question: str,
    allowed_kb_ids: list[UUID],
    scoped_kb_codes: list[str],
    top_k: int | None = None,
    runtime: RetrievalRuntime | None = None,
) -> list[RetrievedChunk]:
    if not allowed_kb_ids:
        return []

    limit = top_k or settings.qa_top_k
    allowed_set = _to_uuid_set(allowed_kb_ids)

    kb_statement = select(KnowledgeBase).where(KnowledgeBase.id.in_(list(allowed_set)))
    if scoped_kb_codes:
        kb_statement = kb_statement.where(KnowledgeBase.code.in_(scoped_kb_codes))
    kbs = list(db.scalars(kb_statement).all())
    kb_by_id = {kb.id: kb for kb in kbs}
    selected_ids = set(kb_by_id.keys())
    if not selected_ids:
        return []

    retrieval_runtime = runtime or get_retrieval_runtime(db)
    if retrieval_runtime.retrieval_engine == RETRIEVAL_ENGINE_PGVECTOR_SQL:
        try:
            # Critical security property: SQL vector retrieval is always scoped by selected_ids in WHERE.
            return _retrieve_with_pgvector_sql(
                db=db,
                question=question,
                kb_by_id=kb_by_id,
                selected_ids=selected_ids,
                limit=limit,
            )
        except Exception:
            retrieval_runtime.retrieval_engine = RETRIEVAL_ENGINE_PYTHON_FALLBACK
            retrieval_runtime.sql_vector_search_enabled = False
            retrieval_runtime.fallback_reason = "pgvector_sql_runtime_error"
            # Keep service availability if pgvector SQL path is unavailable at runtime.
            return _retrieve_with_python_cosine_fallback(
                db=db,
                question=question,
                kb_by_id=kb_by_id,
                selected_ids=selected_ids,
                limit=limit,
            )

    return _retrieve_with_python_cosine_fallback(
        db=db,
        question=question,
        kb_by_id=kb_by_id,
        selected_ids=selected_ids,
        limit=limit,
    )
