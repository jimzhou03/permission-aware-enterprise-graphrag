from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.schemas.qa import AskRequest, AskResponse, Citation
from app.services.audit_service import create_qa_audit_log
from app.services.local_router_service import route_question
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.rag_service import retrieve_permission_scoped_chunks


settings = get_settings()


@dataclass
class QAResult:
    response: AskResponse
    request_id: str


def _deny_response(request_id: str, reason: str, route_mode: str, route) -> AskResponse:
    return AskResponse(
        request_id=request_id,
        answer="Access denied: you are not allowed to access the requested knowledge scope.",
        denied=True,
        refusal_reason=reason,
        cache_hit=False,
        mode=route_mode,  # type: ignore[arg-type]
        route=route,
        citations=[],
        graph_paths=[],
    )


def _render_answer(citations: list[Citation]) -> str:
    if not citations:
        return "No relevant authorized documents were found."
    lines = ["Authorized answer generated from the following scoped knowledge:"]
    for idx, citation in enumerate(citations, start=1):
        lines.append(f"{idx}. [{citation.kb_code}] {citation.document_title}: {citation.excerpt}")
    return "\n".join(lines)


def ask_question(db: Session, user: User, payload: AskRequest) -> QAResult:
    start = time.perf_counter()
    request_id = f"qa_{uuid.uuid4().hex[:16]}"
    route = route_question(payload.question, payload.mode)

    allowed_kbs = list_allowed_knowledge_bases(db, user)
    allowed_kb_ids = [kb.id for kb in allowed_kbs]
    allowed_kb_codes = {kb.code for kb in allowed_kbs}

    if payload.knowledge_base_codes:
        unauthorized = [code for code in payload.knowledge_base_codes if code not in allowed_kb_codes]
        if unauthorized:
            response = _deny_response(
                request_id=request_id,
                reason=f"Requested knowledge base is outside allowed scope: {', '.join(unauthorized)}",
                route_mode=route.mode,
                route=route,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            create_qa_audit_log(
                db=db,
                request_id=request_id,
                user_id=user.id,
                question=payload.question,
                answer=response.answer,
                denied=True,
                refusal_reason=response.refusal_reason or "",
                hit_kb_ids=[],
                hit_document_ids=[],
                hit_chunk_ids=[],
                mode=route.mode,
                model="phase2-mock-llm",
                latency_ms=latency_ms,
                cache_hit=False,
            )
            return QAResult(response=response, request_id=request_id)

    if route.target_department and route.target_department not in {"public"}:
        matches_target = [
            kb for kb in allowed_kbs if kb.department and kb.department.code == route.target_department
        ]
        if not matches_target and user.role and user.role.name != "admin":
            response = _deny_response(
                request_id=request_id,
                reason=f"User cannot access department scope: {route.target_department}",
                route_mode=route.mode,
                route=route,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            create_qa_audit_log(
                db=db,
                request_id=request_id,
                user_id=user.id,
                question=payload.question,
                answer=response.answer,
                denied=True,
                refusal_reason=response.refusal_reason or "",
                hit_kb_ids=[],
                hit_document_ids=[],
                hit_chunk_ids=[],
                mode=route.mode,
                model="phase2-mock-llm",
                latency_ms=latency_ms,
                cache_hit=False,
            )
            return QAResult(response=response, request_id=request_id)

    scoped_codes = payload.knowledge_base_codes
    retrieved = retrieve_permission_scoped_chunks(
        db=db,
        question=payload.question,
        allowed_kb_ids=allowed_kb_ids,
        scoped_kb_codes=scoped_codes,
        top_k=settings.qa_top_k,
    )

    citations: list[Citation] = [
        Citation(
            kb_id=item.kb_id,
            kb_code=item.kb_code,
            kb_name=item.kb_name,
            document_id=item.document_id,
            document_title=item.document_title,
            chunk_id=item.chunk_id,
            score=round(item.score, 4),
            excerpt=item.content[:260],
        )
        for item in retrieved
    ]
    answer = _render_answer(citations)
    response = AskResponse(
        request_id=request_id,
        answer=answer,
        denied=False,
        refusal_reason=None,
        cache_hit=False,
        mode=route.mode,  # type: ignore[arg-type]
        route=route,
        citations=citations,
        graph_paths=[],
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    create_qa_audit_log(
        db=db,
        request_id=request_id,
        user_id=user.id,
        question=payload.question,
        answer=answer,
        denied=False,
        refusal_reason="",
        hit_kb_ids=[str(item.kb_id) for item in citations],
        hit_document_ids=[str(item.document_id) for item in citations],
        hit_chunk_ids=[str(item.chunk_id) for item in citations],
        mode=route.mode,
        model="phase2-mock-llm",
        latency_ms=latency_ms,
        cache_hit=False,
    )
    return QAResult(response=response, request_id=request_id)
