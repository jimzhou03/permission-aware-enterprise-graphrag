from __future__ import annotations

import re
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
from app.services.llm_service import generate_answer
from app.services.local_router_service import get_router_status, route_question
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.qa_runtime_store import RouterTraceSnapshot, qa_runtime_store
from app.services.rag_service import get_retrieval_runtime, retrieve_permission_scoped_chunks


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


def _deny_response(request_id: str, reason: str, route_mode: str, route: RouteDecision) -> AskResponse:
    return AskResponse(
        request_id=request_id,
        answer="Access denied: you are not allowed to access the requested knowledge scope.",
        denied=True,
        refusal_reason=reason,
        cache_hit=False,
        mode=route_mode,  # type: ignore[arg-type]
        route=route,
        router_mode=route.router_mode,
        router_model=route.router_model,
        router_fallback_used=route.router_fallback_used,
        router_error=route.router_error,
        retrieved_chunks=[],
        citations=[],
        graph_paths=[],
    )


def _model_profile(retrieval_token: str) -> str:
    router_model = settings.ollama_router_model if settings.local_router_mode == "ollama" else "rules"
    return (
        f"llm={settings.llm_mode}:{settings.llm_model}|"
        f"router={settings.local_router_mode}:{router_model}|"
        f"retrieval={retrieval_token}"
    )


def _cache_payload_from_response(response: AskResponse, model: str) -> dict:
    return {
        "answer": response.answer,
        "denied": response.denied,
        "refusal_reason": response.refusal_reason,
        "mode": response.mode,
        "model": model,
        "route": response.route.model_dump(),
        "router_mode": response.router_mode,
        "router_model": response.router_model,
        "router_fallback_used": response.router_fallback_used,
        "router_error": response.router_error,
        "retrieved_chunks": [item.model_dump(mode="json") for item in response.retrieved_chunks],
        "citations": [item.model_dump(mode="json") for item in response.citations],
        "graph_paths": [item.model_dump(mode="json") for item in response.graph_paths],
    }


def _response_from_cache_payload(request_id: str, payload: dict) -> AskResponse:
    route = RouteDecision(**payload.get("route", {}))
    retrieved_chunks = [Citation(**item) for item in payload.get("retrieved_chunks", [])]
    citations = [Citation(**item) for item in payload.get("citations", [])]
    graph_paths = [GraphPath(**item) for item in payload.get("graph_paths", [])]
    if not retrieved_chunks and citations:
        retrieved_chunks = citations
    return AskResponse(
        request_id=request_id,
        answer=payload.get("answer", ""),
        denied=bool(payload.get("denied", False)),
        refusal_reason=payload.get("refusal_reason"),
        cache_hit=True,
        mode=payload.get("mode", route.mode),
        route=route,
        router_mode=str(payload.get("router_mode", route.router_mode)),
        router_model=str(payload.get("router_model", route.router_model)),
        router_fallback_used=bool(payload.get("router_fallback_used", route.router_fallback_used)),
        router_error=payload.get("router_error", route.router_error),
        retrieved_chunks=retrieved_chunks,
        citations=citations,
        graph_paths=graph_paths,
    )


def _model_from_cache_payload(payload: dict, fallback_retrieval_engine: str) -> str:
    value = payload.get("model")
    model = str(value) if value else "cache:unknown-model"
    if "|retrieval=" in model:
        return model
    return f"{model}|retrieval={fallback_retrieval_engine}"


def _append_retrieval_engine(model: str, retrieval_engine: str) -> str:
    if "|retrieval=" in model:
        return model
    return f"{model}|retrieval={retrieval_engine}"


def _render_general_greeting(question: str) -> str:
    is_zh = bool(re.search(r"[\u4e00-\u9fff]", question))
    if is_zh:
        return "你好，我是企业权限感知知识助手。你可以询问与当前权限范围内知识库相关的问题。"
    return (
        "Hello, I am the permission-aware enterprise knowledge assistant. "
        "You can ask questions within your authorized knowledge bases."
    )


def _record_router_trace(request_id: str, route: RouteDecision, router_availability: str) -> None:
    qa_runtime_store.set_router_trace(
        request_id=request_id,
        snapshot=RouterTraceSnapshot(
            route=route,
            router_mode=route.router_mode,
            router_model=route.router_model,
            router_availability=router_availability,
            router_fallback_used=route.router_fallback_used,
            router_error=route.router_error,
        ),
    )


def ask_question(db: Session, user: User, payload: AskRequest) -> QAResult:
    start = time.perf_counter()
    request_id = f"qa_{uuid.uuid4().hex[:16]}"
    route = route_question(payload.question, payload.mode)
    router_availability = get_router_status().availability

    allowed_kbs = list_allowed_knowledge_bases(db, user)
    allowed_kb_ids = [kb.id for kb in allowed_kbs]
    allowed_kb_codes = {kb.code for kb in allowed_kbs}
    retrieval_runtime = get_retrieval_runtime(db)

    if payload.knowledge_base_codes:
        unauthorized = [code for code in payload.knowledge_base_codes if code not in allowed_kb_codes]
        if unauthorized:
            response = _deny_response(
                request_id=request_id,
                reason=f"Requested knowledge base is outside allowed scope: {', '.join(unauthorized)}",
                route_mode=route.mode,
                route=route,
            )
            _record_router_trace(request_id=request_id, route=route, router_availability=router_availability)
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
                model="permission-deny|retrieval=none",
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
            _record_router_trace(request_id=request_id, route=route, router_availability=router_availability)
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
                model="permission-deny|retrieval=none",
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
        model_profile=_model_profile(retrieval_runtime.cache_token),
        prompt_version=settings.prompt_version,
    )
    cached_payload = cache_service.get_payload(cache_key_parts)
    if cached_payload is not None:
        cached_response = _response_from_cache_payload(request_id, cached_payload)
        _record_router_trace(
            request_id=request_id,
            route=cached_response.route,
            router_availability=router_availability,
        )
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
            model=_model_from_cache_payload(cached_payload, fallback_retrieval_engine=retrieval_runtime.retrieval_engine),
            latency_ms=latency_ms,
            cache_hit=True,
        )
        return QAResult(response=cached_response, request_id=request_id)

    if route.mode == "general":
        answer = _render_general_greeting(payload.question)
        response = AskResponse(
            request_id=request_id,
            answer=answer,
            denied=False,
            refusal_reason=None,
            cache_hit=False,
            mode="general",
            route=route,
            router_mode=route.router_mode,
            router_model=route.router_model,
            router_fallback_used=route.router_fallback_used,
            router_error=route.router_error,
            retrieved_chunks=[],
            citations=[],
            graph_paths=[],
        )
        _record_router_trace(request_id=request_id, route=route, router_availability=router_availability)
        latency_ms = int((time.perf_counter() - start) * 1000)
        create_qa_audit_log(
            db=db,
            request_id=request_id,
            user_id=user.id,
            question=payload.question,
            answer=answer,
            denied=False,
            refusal_reason="",
            hit_kb_ids=[],
            hit_document_ids=[],
            hit_chunk_ids=[],
            mode="general",
            model="general-fallback|retrieval=none",
            latency_ms=latency_ms,
            cache_hit=False,
        )
        cache_service.set_payload(
            cache_key_parts,
            payload=_cache_payload_from_response(response, model="general-fallback|retrieval=none"),
            ttl_seconds=settings.cache_ttl_seconds,
        )
        return QAResult(response=response, request_id=request_id)

    scoped_codes = payload.knowledge_base_codes
    retrieved = retrieve_permission_scoped_chunks(
        db=db,
        question=payload.question,
        allowed_kb_ids=allowed_kb_ids,
        scoped_kb_codes=scoped_codes,
        top_k=settings.qa_top_k,
        runtime=retrieval_runtime,
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

    generated = generate_answer(
        question=payload.question,
        citations=citations,
        graph_paths=graph_paths,
    )
    answer = generated.answer
    response = AskResponse(
        request_id=request_id,
        answer=answer,
        denied=False,
        refusal_reason=None,
        cache_hit=False,
        mode=route.mode,  # type: ignore[arg-type]
        route=route,
        router_mode=route.router_mode,
        router_model=route.router_model,
        router_fallback_used=route.router_fallback_used,
        router_error=route.router_error,
        retrieved_chunks=citations,
        citations=citations,
        graph_paths=graph_paths,
    )
    _record_router_trace(request_id=request_id, route=route, router_availability=router_availability)
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
        model=_append_retrieval_engine(generated.model, retrieval_runtime.retrieval_engine),
        latency_ms=latency_ms,
        cache_hit=False,
    )

    ttl_seconds = settings.cache_refusal_ttl_seconds if response.denied else settings.cache_ttl_seconds
    cache_service.set_payload(
        cache_key_parts,
        payload=_cache_payload_from_response(
            response,
            model=_append_retrieval_engine(generated.model, retrieval_runtime.retrieval_engine),
        ),
        ttl_seconds=ttl_seconds,
    )
    return QAResult(response=response, request_id=request_id)
