from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models import Document, DocumentChunk, KnowledgeBase, User
from app.schemas.graph import QAGraphResponse
from app.schemas.qa import (
    AskRequest,
    AskResponse,
    Citation,
    FunctionTraceStep,
    QAAuditRecordResponse,
    QATraceResponse,
    RouteDecision,
    TraceRetrievedChunk,
)
from app.services.audit_service import get_qa_audit_by_request_id
from app.services.auth_service import user_has_permission
from app.services.graph_service import (
    build_graph_elements_from_chunk_rows,
    build_graph_paths_for_citations,
    neo4j_service,
)
from app.services.local_router_service import get_router_status
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.qa_service import ask_question
from app.services.qa_runtime_store import qa_runtime_store
from app.services.rag_service import get_retrieval_runtime


router = APIRouter(prefix="/qa", tags=["qa"])


def _parse_uuid_list(values: list[str]) -> list[UUID]:
    parsed: list[UUID] = []
    for value in values:
        try:
            parsed.append(UUID(value))
        except ValueError:
            continue
    return parsed


def _parse_retrieval_engine_from_model(model: str) -> str | None:
    marker = "|retrieval="
    if marker not in model:
        return None
    return model.split(marker, maxsplit=1)[1].strip() or None


def _default_router_decision(record_mode: str) -> RouteDecision:
    need_rag = record_mode in {"rag", "graphrag"}
    return RouteDecision(
        target_department=None,
        mode=record_mode if record_mode in {"general", "rag", "graphrag"} else "rag",  # type: ignore[arg-type]
        requires_rag=need_rag,
        need_rag=need_rag,
        confidence=0.0,
        reason="router decision was not persisted for this historical request.",
    )


def _default_function_trace(record_mode: str, denied: bool, cache_hit: bool) -> list[FunctionTraceStep]:
    security_notes = {
        "classify_query": "Router only classifies intent and mode; permission authority stays in backend RBAC.",
        "resolve_user_permission_scope": "Allowed knowledge scope is resolved by backend RBAC and ACL only.",
        "check_cache": "Cache keys are permission-scoped and cannot expand access boundaries.",
        "search_allowed_chunks": "Retrieval runs only inside backend allowed_kb_ids before returning any chunk.",
        "get_graph_paths": "Graph projection only uses already authorized citation chunk identifiers.",
        "generate_answer": "Answer generation uses authorized retrieval output; autonomous tool calling is disabled.",
        "save_audit_log": "Audit stores safe metadata and avoids unauthorized chunk content disclosure.",
    }
    steps: list[tuple[str, str, str, str, str | None]] = [
        (
            "classify_query",
            "success",
            "historical_reconstruction",
            "router_trace_missing_runtime_snapshot",
            None,
        ),
        (
            "resolve_user_permission_scope",
            "success",
            "historical_reconstruction",
            "permission_scope_reconstructed",
            None,
        ),
    ]
    if cache_hit:
        steps.extend(
            [
                ("check_cache", "success", "historical_reconstruction", "cache_hit=true", None),
                ("search_allowed_chunks", "skipped", "cache_hit=true", "cache_hit_skip_retrieval", None),
                ("get_graph_paths", "skipped", "cache_hit=true", "cache_hit_skip_graph_projection", None),
                ("generate_answer", "skipped", "cache_hit=true", "cached_answer", None),
            ]
        )
    elif denied:
        steps.extend(
            [
                (
                    "check_cache",
                    "skipped",
                    "historical_reconstruction",
                    "permission_denied_path",
                    None,
                ),
                ("search_allowed_chunks", "denied", "historical_reconstruction", "permission_denied", None),
                ("get_graph_paths", "skipped", "permission_denied", "denied_before_retrieval", None),
                ("generate_answer", "skipped", "permission_denied", "permission_denied", None),
            ]
        )
    elif record_mode == "general":
        steps.extend(
            [
                ("check_cache", "success", "historical_reconstruction", "cache_hit=false_or_not_persisted", None),
                ("search_allowed_chunks", "skipped", "mode=general", "router_need_rag=false", None),
                ("get_graph_paths", "skipped", "mode=general", "general_mode_no_graph_projection", None),
                ("generate_answer", "success", "general_fallback", "general_fallback_response", None),
            ]
        )
    else:
        steps.extend(
            [
                ("check_cache", "success", "historical_reconstruction", "cache_hit=false_or_not_persisted", None),
                ("search_allowed_chunks", "success", "historical_reconstruction", "retrieval_executed", None),
                (
                    "get_graph_paths",
                    "success" if record_mode == "graphrag" else "skipped",
                    f"mode={record_mode}",
                    "graph_projection_executed" if record_mode == "graphrag" else "graph_projection_not_requested",
                    None,
                ),
                ("generate_answer", "success", "historical_reconstruction", "answer_generated", None),
            ]
        )
    steps.append(("save_audit_log", "success", "historical_reconstruction", "audit_saved", None))
    return [
        FunctionTraceStep(
            tool_name=tool_name,
            status=status,  # type: ignore[arg-type]
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=0,
            security_note=security_notes[tool_name],
            error_code=error_code,
            order_index=index,
        )
        for index, (tool_name, status, input_summary, output_summary, error_code) in enumerate(steps, start=1)
    ]


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


@router.get("/{request_id}/trace", response_model=QATraceResponse)
def get_request_trace(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QATraceResponse:
    record = get_qa_audit_by_request_id(db, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request record not found")

    is_owner = record.user_id is not None and record.user_id == current_user.id
    can_read_audit = user_has_permission(db, current_user, "audit:read")
    if not is_owner and not can_read_audit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this trace")

    viewer_allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    viewer_allowed_kb_ids = {kb.id for kb in viewer_allowed_kbs}

    request_user = record.user
    request_allowed_kbs = list_allowed_knowledge_bases(db, request_user) if request_user else []
    allowed_kb_ids = [str(kb.id) for kb in request_allowed_kbs]
    allowed_kb_codes = [kb.code for kb in request_allowed_kbs]
    current_runtime = get_retrieval_runtime(db)
    current_router_status = get_router_status()
    route_snapshot = qa_runtime_store.get_router_trace(request_id)
    route_decision = route_snapshot.route if route_snapshot else _default_router_decision(record.mode)
    function_trace = (
        route_snapshot.function_trace
        if route_snapshot and route_snapshot.function_trace
        else _default_function_trace(record.mode, denied=record.denied, cache_hit=record.cache_hit)
    )

    hit_kb_ids = record.hit_kb_ids if isinstance(record.hit_kb_ids, list) else []
    hit_document_ids = record.hit_document_ids if isinstance(record.hit_document_ids, list) else []
    hit_chunk_ids = record.hit_chunk_ids if isinstance(record.hit_chunk_ids, list) else []

    hit_chunk_uuid_list = _parse_uuid_list(hit_chunk_ids)
    chunk_rows = db.execute(
        select(DocumentChunk, Document, KnowledgeBase)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(KnowledgeBase, KnowledgeBase.id == DocumentChunk.knowledge_base_id)
        .where(DocumentChunk.id.in_(hit_chunk_uuid_list))
    ).all()
    row_by_chunk_id = {str(chunk.id): (chunk, document, kb) for chunk, document, kb in chunk_rows}

    reconstructed_chunks: list[TraceRetrievedChunk] = []
    omitted_for_scope = 0
    for chunk_id in hit_chunk_ids:
        row = row_by_chunk_id.get(chunk_id)
        if row is None:
            continue
        chunk, document, kb = row
        if kb.id not in viewer_allowed_kb_ids:
            omitted_for_scope += 1
            continue
        embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
        preview = chunk.content.strip().replace("\n", " ")
        if len(preview) > 220:
            preview = f"{preview[:220]}..."
        reconstructed_chunks.append(
            TraceRetrievedChunk(
                chunk_id=chunk.id,
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=document.id,
                document_title=document.title,
                chunk_index=chunk.ordinal,
                content_preview=preview,
                content=chunk.content,
                has_embedding=bool(embedding),
                embedding_dimension=len(embedding),
            )
        )

    trace_limits = [
        "retrieved_chunks are reconstructed from current document_chunks using hit_chunk_ids; historical full snapshots are not persisted in qa_audit_logs.",
        "allowed_kb_ids are reconstructed from current ACL scope and may differ from historical scope at request time.",
    ]
    if omitted_for_scope > 0:
        trace_limits.append(
            f"{omitted_for_scope} chunk(s) were omitted because current viewer scope does not allow their knowledge base."
        )
    if hit_chunk_ids and not reconstructed_chunks:
        trace_limits.append(
            "No authorized chunk content is available to current viewer; trace falls back to identifier-level metadata."
        )
    if route_snapshot is None:
        trace_limits.append(
            "router diagnostics are available for recent runtime requests only; this trace shows reconstructed defaults."
        )
    if not route_snapshot or not route_snapshot.function_trace:
        trace_limits.append(
            "function trace is reconstructed from audit metadata when runtime step snapshots are unavailable."
        )

    return QATraceResponse(
        request_id=record.request_id,
        user_id=record.user_id,
        user_email=request_user.email if request_user else None,
        role=request_user.role.name if request_user and request_user.role else None,
        department=request_user.department.code if request_user and request_user.department else None,
        question=record.question,
        answer=record.answer,
        mode=record.mode,
        denied=record.denied,
        refusal_reason=record.refusal_reason,
        allowed_kb_ids=allowed_kb_ids,
        allowed_kb_codes=allowed_kb_codes,
        hit_kb_ids=hit_kb_ids,
        hit_document_ids=hit_document_ids,
        hit_chunk_ids=hit_chunk_ids,
        retrieved_chunks=reconstructed_chunks,
        retrieval_engine=(
            _parse_retrieval_engine_from_model(record.model) or current_runtime.retrieval_engine
        ),
        router_mode=route_snapshot.router_mode if route_snapshot else current_router_status.mode,
        router_model=route_snapshot.router_model if route_snapshot else current_router_status.model,
        router_availability=(
            route_snapshot.router_availability if route_snapshot else current_router_status.availability
        ),
        router_fallback_used=(
            route_snapshot.router_fallback_used if route_snapshot else current_router_status.fallback_used
        ),
        router_error=route_snapshot.router_error if route_snapshot else current_router_status.error,
        router_decision=route_decision,
        cache_hit=record.cache_hit,
        model=record.model,
        latency_ms=record.latency_ms,
        function_trace=function_trace,
        trace_limits=trace_limits,
    )


@router.get("/{request_id}/graph", response_model=QAGraphResponse)
def get_request_graph(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QAGraphResponse:
    record = get_qa_audit_by_request_id(db, request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request record not found")

    is_owner = record.user_id is not None and record.user_id == current_user.id
    can_read_audit = user_has_permission(db, current_user, "audit:read")
    if not is_owner and not can_read_audit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden to read this graph trace")

    viewer_allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    viewer_allowed_kb_ids = {kb.id for kb in viewer_allowed_kbs}
    request_user = record.user
    request_allowed_kbs = list_allowed_knowledge_bases(db, request_user) if request_user else []
    request_allowed_ids = [kb.id for kb in request_allowed_kbs]
    allowed_kb_ids = [str(kb.id) for kb in request_allowed_kbs]
    allowed_kb_codes = [kb.code for kb in request_allowed_kbs]

    hit_chunk_ids = record.hit_chunk_ids if isinstance(record.hit_chunk_ids, list) else []
    hit_chunk_uuid_list = _parse_uuid_list(hit_chunk_ids)
    chunk_rows = db.execute(
        select(DocumentChunk, Document, KnowledgeBase)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(KnowledgeBase, KnowledgeBase.id == DocumentChunk.knowledge_base_id)
        .where(DocumentChunk.id.in_(hit_chunk_uuid_list))
    ).all()
    row_by_chunk_id = {str(chunk.id): (chunk, document, kb) for chunk, document, kb in chunk_rows}

    authorized_rows: list[tuple[DocumentChunk, Document, KnowledgeBase]] = []
    omitted_for_scope = 0
    for chunk_id in hit_chunk_ids:
        row = row_by_chunk_id.get(chunk_id)
        if row is None:
            continue
        chunk, _, kb = row
        if kb.id not in viewer_allowed_kb_ids:
            omitted_for_scope += 1
            continue
        authorized_rows.append(row)

    citations: list[Citation] = []
    for chunk, document, kb in authorized_rows:
        preview = chunk.content.strip().replace("\n", " ")
        if len(preview) > 220:
            preview = f"{preview[:220]}..."
        citations.append(
            Citation(
                kb_id=kb.id,
                kb_code=kb.code,
                kb_name=kb.name,
                document_id=document.id,
                document_title=document.title,
                chunk_id=chunk.id,
                score=0.0,
                excerpt=preview,
            )
        )

    effective_allowed_ids = [kb_id for kb_id in request_allowed_ids if kb_id in viewer_allowed_kb_ids]
    graph_paths = (
        build_graph_paths_for_citations(db=db, citations=citations, allowed_kb_ids=effective_allowed_ids)
        if record.mode == "graphrag" and citations
        else []
    )
    nodes, edges = build_graph_elements_from_chunk_rows(
        authorized_rows,
        include_chunk_preview=True,
    )

    graph_status = neo4j_service.get_status()
    local_projection_used = any(
        "local entity projection" in item.explanation.lower()
        for item in graph_paths
    )
    fallback_used = (not bool(graph_status.get("neo4j_available"))) or local_projection_used

    security_notes = [
        "Graph nodes and edges are filtered by current viewer backend RBAC scope.",
        "Graph endpoint does not expose full chunk content.",
    ]
    if omitted_for_scope > 0:
        security_notes.append(
            f"{omitted_for_scope} chunk-linked graph segment(s) were omitted due to current viewer scope."
        )
    if hit_chunk_ids and not authorized_rows:
        security_notes.append("No authorized graph segment is visible to current viewer for this request.")
    if record.mode != "graphrag":
        security_notes.append("Request mode is not graphrag; graph path projection is not requested.")

    return QAGraphResponse(
        request_id=record.request_id,
        mode=record.mode,
        viewer_email=current_user.email,
        viewer_role=current_user.role.name if current_user.role else None,
        viewer_department=current_user.department.code if current_user.department else None,
        allowed_kb_ids=allowed_kb_ids,
        allowed_kb_codes=allowed_kb_codes,
        graph_paths=graph_paths,
        nodes=nodes,
        edges=edges,
        fallback_used=fallback_used,
        security_notes=security_notes,
    )
