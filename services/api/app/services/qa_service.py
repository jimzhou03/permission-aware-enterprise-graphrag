from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.schemas.qa import AskRequest, AskResponse, Citation, FunctionTraceStep, GraphPath, RouteDecision
from app.services.audit_service import create_qa_audit_log
from app.services.cache_service import build_cache_key_parts, cache_service
from app.services.graph_service import build_graph_paths_for_citations
from app.services.llm_service import generate_answer
from app.services.local_router_service import get_router_status, route_question
from app.services.permission_service import list_allowed_knowledge_bases
from app.services.qa_runtime_store import RouterTraceSnapshot, qa_runtime_store
from app.services.rag_service import get_retrieval_runtime, retrieve_permission_scoped_chunks


settings = get_settings()

TRACE_STEP_ORDER = [
    "classify_query",
    "resolve_user_permission_scope",
    "check_cache",
    "search_allowed_chunks",
    "get_graph_paths",
    "generate_answer",
    "save_audit_log",
]

TRACE_STEP_SECURITY_NOTES = {
    "classify_query": "Router only classifies intent and mode; permission authority stays in backend RBAC.",
    "resolve_user_permission_scope": "Allowed knowledge scope is resolved by backend RBAC and ACL only.",
    "check_cache": "Cache keys are permission-scoped and cannot expand access boundaries.",
    "search_allowed_chunks": "Retrieval runs only inside backend allowed_kb_ids before returning any chunk.",
    "get_graph_paths": "Graph projection only uses already authorized citation chunk identifiers.",
    "generate_answer": "Answer generation uses authorized retrieval output; autonomous tool calling is disabled.",
    "save_audit_log": "Audit stores safe metadata and avoids unauthorized chunk content disclosure.",
}


@dataclass
class QAResult:
    response: AskResponse
    request_id: str


class _FunctionTraceRecorder:
    def __init__(self) -> None:
        self._steps: dict[str, FunctionTraceStep] = {}
        for index, name in enumerate(TRACE_STEP_ORDER, start=1):
            self._steps[name] = FunctionTraceStep(
                tool_name=name,
                status="skipped",
                input_summary="not_executed",
                output_summary="not_executed",
                duration_ms=0,
                security_note=TRACE_STEP_SECURITY_NOTES.get(name, ""),
                order_index=index,
            )

    def set_step(
        self,
        *,
        tool_name: str,
        status: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int,
        error_code: str | None = None,
    ) -> None:
        existing = self._steps[tool_name]
        self._steps[tool_name] = FunctionTraceStep(
            tool_name=tool_name,
            status=status,  # type: ignore[arg-type]
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=max(duration_ms, 0),
            security_note=existing.security_note,
            error_code=error_code,
            order_index=existing.order_index,
        )

    def build(self) -> list[FunctionTraceStep]:
        return [self._steps[name] for name in TRACE_STEP_ORDER]

    def summary(self) -> list[str]:
        return [f"{step.order_index}.{step.tool_name}:{step.status}" for step in self.build()]


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


def _record_router_trace(
    request_id: str,
    route: RouteDecision,
    router_availability: str,
    function_trace: list[FunctionTraceStep],
) -> None:
    qa_runtime_store.set_router_trace(
        request_id=request_id,
        snapshot=RouterTraceSnapshot(
            route=route,
            router_mode=route.router_mode,
            router_model=route.router_model,
            router_availability=router_availability,
            router_fallback_used=route.router_fallback_used,
            router_error=route.router_error,
            function_trace=function_trace,
        ),
    )


def _finalize_with_audit(
    *,
    db: Session,
    start: float,
    request_id: str,
    user: User,
    question: str,
    response: AskResponse,
    model: str,
    router_availability: str,
    trace_recorder: _FunctionTraceRecorder,
) -> QAResult:
    latency_ms = int((time.perf_counter() - start) * 1000)

    save_input = f"request_id={request_id} denied={response.denied} cache_hit={response.cache_hit}"
    save_start = time.perf_counter()
    try:
        create_qa_audit_log(
            db=db,
            request_id=request_id,
            user_id=user.id,
            question=question,
            answer=response.answer,
            denied=response.denied,
            refusal_reason=response.refusal_reason or "",
            hit_kb_ids=_as_unique_strings(str(item.kb_id) for item in response.citations),
            hit_document_ids=_as_unique_strings(str(item.document_id) for item in response.citations),
            hit_chunk_ids=_as_unique_strings(str(item.chunk_id) for item in response.citations),
            mode=response.mode,
            model=model,
            latency_ms=latency_ms,
            cache_hit=response.cache_hit,
        )
    except Exception:
        save_duration_ms = int((time.perf_counter() - save_start) * 1000)
        trace_recorder.set_step(
            tool_name="save_audit_log",
            status="error",
            input_summary=save_input,
            output_summary="audit_log_write_failed",
            duration_ms=save_duration_ms,
            error_code="audit_log_write_error",
        )
        _record_router_trace(
            request_id=request_id,
            route=response.route,
            router_availability=router_availability,
            function_trace=trace_recorder.build(),
        )
        raise

    save_duration_ms = int((time.perf_counter() - save_start) * 1000)
    trace_recorder.set_step(
        tool_name="save_audit_log",
        status="success",
        input_summary=save_input,
        output_summary=f"audit_saved latency_ms={latency_ms}",
        duration_ms=save_duration_ms,
    )
    response.function_trace_summary = trace_recorder.summary()
    _record_router_trace(
        request_id=request_id,
        route=response.route,
        router_availability=router_availability,
        function_trace=trace_recorder.build(),
    )
    return QAResult(response=response, request_id=request_id)


def ask_question(db: Session, user: User, payload: AskRequest) -> QAResult:
    start = time.perf_counter()
    request_id = f"qa_{uuid.uuid4().hex[:16]}"
    trace_recorder = _FunctionTraceRecorder()

    classify_input = f"mode={payload.mode} question_len={len(payload.question)}"
    classify_start = time.perf_counter()
    try:
        route = route_question(payload.question, payload.mode)
    except Exception:
        classify_duration_ms = int((time.perf_counter() - classify_start) * 1000)
        trace_recorder.set_step(
            tool_name="classify_query",
            status="error",
            input_summary=classify_input,
            output_summary="router_classification_failed",
            duration_ms=classify_duration_ms,
            error_code="router_error",
        )
        raise
    classify_duration_ms = int((time.perf_counter() - classify_start) * 1000)
    trace_recorder.set_step(
        tool_name="classify_query",
        status="success",
        input_summary=classify_input,
        output_summary=(
            f"mode={route.mode} need_rag={route.need_rag} "
            f"target_department={route.target_department or 'none'}"
        ),
        duration_ms=classify_duration_ms,
    )
    router_availability = get_router_status().availability

    resolve_input = (
        f"role={user.role.name if user.role else 'unknown'} "
        f"department={user.department.code if user.department else 'none'} "
        f"requested_kbs={len(payload.knowledge_base_codes)}"
    )
    resolve_start = time.perf_counter()
    try:
        allowed_kbs = list_allowed_knowledge_bases(db, user)
    except Exception:
        resolve_duration_ms = int((time.perf_counter() - resolve_start) * 1000)
        trace_recorder.set_step(
            tool_name="resolve_user_permission_scope",
            status="error",
            input_summary=resolve_input,
            output_summary="permission_scope_resolution_failed",
            duration_ms=resolve_duration_ms,
            error_code="permission_scope_error",
        )
        raise
    resolve_duration_ms = int((time.perf_counter() - resolve_start) * 1000)
    allowed_kb_ids = [kb.id for kb in allowed_kbs]
    allowed_kb_codes = {kb.code for kb in allowed_kbs}
    trace_recorder.set_step(
        tool_name="resolve_user_permission_scope",
        status="success",
        input_summary=resolve_input,
        output_summary=f"allowed_kbs={len(allowed_kbs)}",
        duration_ms=resolve_duration_ms,
    )
    retrieval_runtime = get_retrieval_runtime(db)

    if payload.knowledge_base_codes:
        unauthorized = [code for code in payload.knowledge_base_codes if code not in allowed_kb_codes]
        if unauthorized:
            trace_recorder.set_step(
                tool_name="check_cache",
                status="skipped",
                input_summary="cache_lookup_not_started",
                output_summary="permission_denied_before_cache",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="search_allowed_chunks",
                status="denied",
                input_summary=f"requested_kbs={len(payload.knowledge_base_codes)}",
                output_summary="requested_scope_outside_allowed_kb_ids",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="get_graph_paths",
                status="skipped",
                input_summary=f"mode={route.mode}",
                output_summary="denied_before_retrieval",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="generate_answer",
                status="skipped",
                input_summary="denied_request",
                output_summary="permission_denied",
                duration_ms=0,
            )
            response = _deny_response(
                request_id=request_id,
                reason=f"Requested knowledge base is outside allowed scope: {', '.join(unauthorized)}",
                route_mode=route.mode,
                route=route,
            )
            return _finalize_with_audit(
                db=db,
                start=start,
                request_id=request_id,
                user=user,
                question=payload.question,
                response=response,
                model="permission-deny|retrieval=none",
                router_availability=router_availability,
                trace_recorder=trace_recorder,
            )

    if route.target_department and route.target_department not in {"public"}:
        matches_target = [
            kb for kb in allowed_kbs if kb.department and kb.department.code == route.target_department
        ]
        if not matches_target and user.role and user.role.name != "admin":
            trace_recorder.set_step(
                tool_name="check_cache",
                status="skipped",
                input_summary="cache_lookup_not_started",
                output_summary="permission_denied_before_cache",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="search_allowed_chunks",
                status="denied",
                input_summary=f"target_department={route.target_department}",
                output_summary="department_scope_not_allowed",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="get_graph_paths",
                status="skipped",
                input_summary=f"mode={route.mode}",
                output_summary="denied_before_retrieval",
                duration_ms=0,
            )
            trace_recorder.set_step(
                tool_name="generate_answer",
                status="skipped",
                input_summary="denied_request",
                output_summary="permission_denied",
                duration_ms=0,
            )
            response = _deny_response(
                request_id=request_id,
                reason=f"User cannot access department scope: {route.target_department}",
                route_mode=route.mode,
                route=route,
            )
            return _finalize_with_audit(
                db=db,
                start=start,
                request_id=request_id,
                user=user,
                question=payload.question,
                response=response,
                model="permission-deny|retrieval=none",
                router_availability=router_availability,
                trace_recorder=trace_recorder,
            )

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
    cache_input = (
        f"mode={route.mode} scoped_kbs={len(payload.knowledge_base_codes)} "
        f"allowed_kbs={len(allowed_kbs)}"
    )
    cache_start = time.perf_counter()
    try:
        cached_payload = cache_service.get_payload(cache_key_parts)
    except Exception:
        cache_duration_ms = int((time.perf_counter() - cache_start) * 1000)
        trace_recorder.set_step(
            tool_name="check_cache",
            status="error",
            input_summary=cache_input,
            output_summary="cache_lookup_failed",
            duration_ms=cache_duration_ms,
            error_code="cache_lookup_error",
        )
        raise
    cache_duration_ms = int((time.perf_counter() - cache_start) * 1000)
    if cached_payload is not None:
        trace_recorder.set_step(
            tool_name="check_cache",
            status="success",
            input_summary=cache_input,
            output_summary="cache_hit=true",
            duration_ms=cache_duration_ms,
        )
        trace_recorder.set_step(
            tool_name="search_allowed_chunks",
            status="skipped",
            input_summary=f"mode={route.mode}",
            output_summary="cache_hit_skip_retrieval",
            duration_ms=0,
        )
        trace_recorder.set_step(
            tool_name="get_graph_paths",
            status="skipped",
            input_summary=f"mode={route.mode}",
            output_summary="cache_hit_skip_graph_projection",
            duration_ms=0,
        )
        trace_recorder.set_step(
            tool_name="generate_answer",
            status="skipped",
            input_summary="cache_hit=true",
            output_summary="cached_answer",
            duration_ms=0,
        )
        cached_response = _response_from_cache_payload(request_id, cached_payload)
        return _finalize_with_audit(
            db=db,
            start=start,
            request_id=request_id,
            user=user,
            question=payload.question,
            response=cached_response,
            model=_model_from_cache_payload(cached_payload, fallback_retrieval_engine=retrieval_runtime.retrieval_engine),
            router_availability=router_availability,
            trace_recorder=trace_recorder,
        )

    trace_recorder.set_step(
        tool_name="check_cache",
        status="success",
        input_summary=cache_input,
        output_summary="cache_hit=false",
        duration_ms=cache_duration_ms,
    )

    if route.mode == "general":
        trace_recorder.set_step(
            tool_name="search_allowed_chunks",
            status="skipped",
            input_summary=f"mode={route.mode}",
            output_summary="router_need_rag=false",
            duration_ms=0,
        )
        trace_recorder.set_step(
            tool_name="get_graph_paths",
            status="skipped",
            input_summary=f"mode={route.mode}",
            output_summary="general_mode_no_graph_projection",
            duration_ms=0,
        )
        answer_start = time.perf_counter()
        answer = _render_general_greeting(payload.question)
        answer_duration_ms = int((time.perf_counter() - answer_start) * 1000)
        trace_recorder.set_step(
            tool_name="generate_answer",
            status="success",
            input_summary="general_fallback",
            output_summary=f"answer_chars={len(answer)}",
            duration_ms=answer_duration_ms,
        )
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
        result = _finalize_with_audit(
            db=db,
            start=start,
            request_id=request_id,
            user=user,
            question=payload.question,
            response=response,
            model="general-fallback|retrieval=none",
            router_availability=router_availability,
            trace_recorder=trace_recorder,
        )
        cache_service.set_payload(
            cache_key_parts,
            payload=_cache_payload_from_response(response, model="general-fallback|retrieval=none"),
            ttl_seconds=settings.cache_ttl_seconds,
        )
        return result

    scoped_codes = payload.knowledge_base_codes
    search_input = (
        f"mode={route.mode} allowed_kbs={len(allowed_kb_ids)} "
        f"scoped_kbs={len(scoped_codes)} top_k={settings.qa_top_k}"
    )
    search_start = time.perf_counter()
    try:
        retrieved = retrieve_permission_scoped_chunks(
            db=db,
            question=payload.question,
            allowed_kb_ids=allowed_kb_ids,
            scoped_kb_codes=scoped_codes,
            top_k=settings.qa_top_k,
            runtime=retrieval_runtime,
        )
    except Exception:
        search_duration_ms = int((time.perf_counter() - search_start) * 1000)
        trace_recorder.set_step(
            tool_name="search_allowed_chunks",
            status="error",
            input_summary=search_input,
            output_summary="retrieval_failed",
            duration_ms=search_duration_ms,
            error_code="retrieval_error",
        )
        raise
    search_duration_ms = int((time.perf_counter() - search_start) * 1000)

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
    hit_codes = {item.kb_code for item in citations}
    trace_recorder.set_step(
        tool_name="search_allowed_chunks",
        status="success",
        input_summary=search_input,
        output_summary=f"hit_chunks={len(citations)} hit_kb_count={len(hit_codes)}",
        duration_ms=search_duration_ms,
    )

    graph_paths: list[GraphPath] = []
    if route.mode == "graphrag":
        graph_input = f"citations={len(citations)} allowed_kbs={len(allowed_kb_ids)}"
        graph_start = time.perf_counter()
        try:
            graph_paths = build_graph_paths_for_citations(
                db=db,
                citations=citations,
                allowed_kb_ids=allowed_kb_ids,
            )
        except Exception:
            graph_duration_ms = int((time.perf_counter() - graph_start) * 1000)
            trace_recorder.set_step(
                tool_name="get_graph_paths",
                status="error",
                input_summary=graph_input,
                output_summary="graph_projection_failed",
                duration_ms=graph_duration_ms,
                error_code="graph_projection_error",
            )
            raise
        graph_duration_ms = int((time.perf_counter() - graph_start) * 1000)
        trace_recorder.set_step(
            tool_name="get_graph_paths",
            status="success",
            input_summary=graph_input,
            output_summary=f"graph_paths={len(graph_paths)}",
            duration_ms=graph_duration_ms,
        )
    else:
        trace_recorder.set_step(
            tool_name="get_graph_paths",
            status="skipped",
            input_summary=f"mode={route.mode}",
            output_summary="graph_projection_not_requested",
            duration_ms=0,
        )

    generate_input = f"citations={len(citations)} graph_paths={len(graph_paths)} llm_mode={settings.llm_mode}"
    generate_start = time.perf_counter()
    try:
        generated = generate_answer(
            question=payload.question,
            citations=citations,
            graph_paths=graph_paths,
        )
    except Exception:
        generate_duration_ms = int((time.perf_counter() - generate_start) * 1000)
        trace_recorder.set_step(
            tool_name="generate_answer",
            status="error",
            input_summary=generate_input,
            output_summary="answer_generation_failed",
            duration_ms=generate_duration_ms,
            error_code="answer_generation_error",
        )
        raise
    answer = generated.answer
    generate_duration_ms = int((time.perf_counter() - generate_start) * 1000)
    trace_recorder.set_step(
        tool_name="generate_answer",
        status="success",
        input_summary=generate_input,
        output_summary=f"model={generated.model} answer_chars={len(answer)}",
        duration_ms=generate_duration_ms,
    )

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
    model = _append_retrieval_engine(generated.model, retrieval_runtime.retrieval_engine)
    result = _finalize_with_audit(
        db=db,
        start=start,
        request_id=request_id,
        user=user,
        question=payload.question,
        response=response,
        model=model,
        router_availability=router_availability,
        trace_recorder=trace_recorder,
    )

    ttl_seconds = settings.cache_refusal_ttl_seconds if response.denied else settings.cache_ttl_seconds
    cache_service.set_payload(
        cache_key_parts,
        payload=_cache_payload_from_response(
            response,
            model=model,
        ),
        ttl_seconds=ttl_seconds,
    )
    return result
