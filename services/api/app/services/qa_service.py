from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.schemas.qa import AskRequest, AskResponse, Citation, GraphPath, RouteDecision
from app.services.audit_service import create_qa_audit_log
from app.services.cache_service import build_cache_key_parts, cache_service
from app.services.graph_service import build_graph_paths_for_citations
from app.services.local_router_service import route_question
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.rag_service import retrieve_permission_scoped_chunks


settings = get_settings()


@dataclass
class QAResult:
    response: AskResponse
    request_id: str


def _as_unique_strings(items: Iterable[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        values.append(item)
    return values


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


def _render_graphrag_answer(citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    base = _render_answer(citations)
    if not graph_paths:
        return base
    lines = [base, "", "Graph evidence paths:"]
    for idx, path in enumerate(graph_paths, start=1):
        lines.append(f"{idx}. {' -> '.join(path.path)}")
    return "\n".join(lines)


def _model_profile() -> str:
    return (
        f"llm={settings.llm_mode}:{settings.llm_model}|"
        f"router={settings.local_router_mode}:{settings.local_router_model}"
    )


def _cache_payload_from_response(response: AskResponse) -> dict:
    return {
        "answer": response.answer,
        "denied": response.denied,
        "refusal_reason": response.refusal_reason,
        "mode": response.mode,
        "route": response.route.model_dump(),
        "citations": [item.model_dump(mode="json") for item in response.citations],
        "graph_paths": [item.model_dump(mode="json") for item in response.graph_paths],
    }


def _response_from_cache_payload(request_id: str, payload: dict) -> AskResponse:
    route = RouteDecision(**payload.get("route", {}))
    citations = [Citation(**item) for item in payload.get("citations", [])]
    graph_paths = [GraphPath(**item) for item in payload.get("graph_paths", [])]
    return AskResponse(
        request_id=request_id,
        answer=payload.get("answer", ""),
        denied=bool(payload.get("denied", False)),
        refusal_reason=payload.get("refusal_reason"),
        cache_hit=True,
        mode=payload.get("mode", route.mode),
        route=route,
        citations=citations,
        graph_paths=graph_paths,
    )


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
                model="phase4-mock-llm",
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
                model="phase4-mock-llm",
                latency_ms=latency_ms,
                cache_hit=False,
            )
            return QAResult(response=response, request_id=request_id)

    cache_key_parts = build_cache_key_parts(
        user_id=str(user.id),
        role=user.role.name if user.role else "",
        department=user.department.code if user.department else None,
        permission_scope_items=[
            f"{settings.permission_policy_version}",
            *(f"{kb.code}:{kb.id}" for kb in allowed_kbs),
        ],
        kb_versions=[f"{kb.code}:{kb.version}" for kb in allowed_kbs],
        question=payload.question,
        mode=route.mode,
        model_profile=_model_profile(),
        prompt_version=settings.prompt_version,
    )
    cached_payload = cache_service.get_payload(cache_key_parts)
    if cached_payload is not None:
        cached_response = _response_from_cache_payload(request_id, cached_payload)
        latency_ms = int((time.perf_counter() - start) * 1000)
        create_qa_audit_log(
            db=db,
            request_id=request_id,
            user_id=user.id,
            question=payload.question,
            answer=cached_response.answer,
            denied=cached_response.denied,
            refusal_reason=cached_response.refusal_reason or "",
            hit_kb_ids=_as_unique_strings(str(item.kb_id) for item in cached_response.citations),
            hit_document_ids=_as_unique_strings(str(item.document_id) for item in cached_response.citations),
            hit_chunk_ids=_as_unique_strings(str(item.chunk_id) for item in cached_response.citations),
            mode=cached_response.mode,
            model="phase4-mock-llm",
            latency_ms=latency_ms,
            cache_hit=True,
        )
        return QAResult(response=cached_response, request_id=request_id)

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
    graph_paths: list[GraphPath] = []
    if route.mode == "graphrag":
        graph_paths = build_graph_paths_for_citations(
            db=db,
            citations=citations,
            allowed_kb_ids=allowed_kb_ids,
        )

    answer = _render_graphrag_answer(citations, graph_paths) if route.mode == "graphrag" else _render_answer(citations)
    response = AskResponse(
        request_id=request_id,
        answer=answer,
        denied=False,
        refusal_reason=None,
        cache_hit=False,
        mode=route.mode,  # type: ignore[arg-type]
        route=route,
        citations=citations,
        graph_paths=graph_paths,
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
        hit_kb_ids=_as_unique_strings(str(item.kb_id) for item in citations),
        hit_document_ids=_as_unique_strings(str(item.document_id) for item in citations),
        hit_chunk_ids=_as_unique_strings(str(item.chunk_id) for item in citations),
        mode=route.mode,
        model="phase4-mock-llm",
        latency_ms=latency_ms,
        cache_hit=False,
    )

    ttl_seconds = settings.cache_refusal_ttl_seconds if response.denied else settings.cache_ttl_seconds
    cache_service.set_payload(
        cache_key_parts,
        payload=_cache_payload_from_response(response),
        ttl_seconds=ttl_seconds,
    )
    return QAResult(response=response, request_id=request_id)
