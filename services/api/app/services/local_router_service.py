from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.schemas.qa import AskMode, RouteDecision, RouterIntent, RouterLanguage, RouterMode, RouterTargetDepartment


settings = get_settings()

DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": ("finance", "salary", "compensation", "payroll", "reimbursement", "budget", "财务", "薪酬", "报销", "预算"),
    "hr": ("hr", "recruit", "hiring", "leave", "attendance", "招聘", "人事", "请假", "考勤"),
    "tech": ("tech", "sdk", "api", "deploy", "release", "incident", "integration", "技术", "发布", "部署"),
    "sales": ("sales", "quote", "pricing", "channel", "deal", "销售", "报价", "客户沟通", "渠道"),
    "marketing": ("marketing", "brand", "campaign", "expo", "market", "市场", "品牌", "展会", "宣传"),
    "support": ("support", "after-sales", "ticket", "warranty", "repair", "客服", "售后", "保修", "工单", "故障"),
    "admin": ("admin", "administration", "meeting room", "procurement", "asset", "行政", "会议室", "采购", "资产"),
    "product": ("product", "spec", "roadmap", "feature", "competition", "产品", "规格", "路线图", "竞品"),
    "cn": ("cn", "chinese", "中文", "汉语", "china policy", "中国内部"),
    "en": ("en", "english", "英文", "internal english", "english internal"),
    "public": ("public", "visitor", "badge", "访客", "公开", "公示"),
}

POLICY_KEYWORDS = (
    "policy",
    "process",
    "procedure",
    "guideline",
    "制度",
    "流程",
    "规范",
    "指引",
)
SECURITY_TEST_KEYWORDS = (
    "secret",
    "confidential",
    "internal only",
    "bypass",
    "override",
    "越权",
    "绕过",
    "机密",
    "内部资料",
)
GREETING_ZH = {"你好", "您好", "早上好", "晚上好"}
GREETING_EN = {"hello", "hi", "good morning", "good evening"}
KNOWN_DEPARTMENTS = {
    "hr",
    "finance",
    "tech",
    "sales",
    "marketing",
    "support",
    "admin",
    "product",
    "cn",
    "en",
    "public",
}


class OllamaRouterOutput(BaseModel):
    language: RouterLanguage
    intent: RouterIntent
    target_department: RouterTargetDepartment
    need_rag: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=240)


@dataclass(frozen=True)
class RouterStatus:
    mode: RouterMode
    model: str
    availability: Literal["available", "unavailable", "not_checked"]
    fallback_used: bool
    error: str | None


class _RouterStatusStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._status = RouterStatus(
            mode=settings.local_router_mode,
            model=_configured_router_model(),
            availability="not_checked",
            fallback_used=False,
            error=None,
        )

    def update(self, status: RouterStatus) -> None:
        with self._lock:
            self._status = status

    def snapshot(self) -> RouterStatus:
        with self._lock:
            return self._status


def _configured_router_model() -> str:
    if settings.local_router_mode == "ollama":
        return settings.ollama_router_model
    return "rules"


_router_status_store = _RouterStatusStore()


def get_router_status() -> RouterStatus:
    return _router_status_store.snapshot()


def _normalize_for_greeting(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_simple_greeting(question: str) -> bool:
    normalized = _normalize_for_greeting(question)
    if not normalized:
        return False
    return normalized in GREETING_EN or normalized in GREETING_ZH


def detect_language(question: str) -> RouterLanguage:
    if re.search(r"[\u4e00-\u9fff]", question):
        return "zh"
    if re.search(r"[a-zA-Z]", question):
        return "en"
    return "unknown"


def detect_target_department(question: str) -> str | None:
    lowered = question.lower()
    public_keywords = DEPARTMENT_KEYWORDS.get("public", ())
    if any(word in lowered for word in public_keywords):
        return "public"
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        if department == "public":
            continue
        if any(word in lowered for word in keywords):
            return department
    return None


def detect_intent(question: str) -> RouterIntent:
    lowered = question.lower()
    if is_simple_greeting(question):
        return "greeting"
    if any(token in lowered for token in SECURITY_TEST_KEYWORDS):
        return "security_test"
    if any(token in lowered for token in POLICY_KEYWORDS):
        return "policy_question"
    if len(lowered.strip()) < 2:
        return "unsupported"
    return "knowledge_lookup"


def _rule_output(question: str) -> OllamaRouterOutput:
    language = detect_language(question)
    intent = detect_intent(question)
    department = detect_target_department(question) or "unknown"
    need_rag = intent not in {"greeting", "unsupported"}
    confidence = 0.98 if intent == "greeting" else (0.88 if department != "unknown" else 0.72)
    reason = "Rule router classification."
    if language == "zh":
        reason = "规则路由分类结果。"
    return OllamaRouterOutput(
        language=language,
        intent=intent,
        target_department=department,  # type: ignore[arg-type]
        need_rag=need_rag,
        confidence=confidence,
        reason=reason,
    )


def _sanitize_department(value: RouterTargetDepartment, question: str) -> str | None:
    if value in KNOWN_DEPARTMENTS:
        return value
    detected = detect_target_department(question)
    if detected in KNOWN_DEPARTMENTS:
        return detected
    return None


def _route_mode_from_inputs(request_mode: AskMode, classification_need_rag: bool, intent: RouterIntent) -> str:
    if request_mode == "graphrag":
        return "graphrag"
    if request_mode == "rag":
        return "rag"
    if intent == "greeting" or not classification_need_rag:
        return "general"
    return "rag"


def _build_route_decision(
    question: str,
    request_mode: AskMode,
    classification: OllamaRouterOutput,
    *,
    router_mode: RouterMode,
    router_model: str,
    router_fallback_used: bool,
    router_error: str | None,
) -> RouteDecision:
    route_mode = _route_mode_from_inputs(request_mode, classification.need_rag, classification.intent)
    if request_mode in {"rag", "graphrag"}:
        need_rag = True
    else:
        need_rag = route_mode in {"rag", "graphrag"}
    target_department = _sanitize_department(classification.target_department, question)
    return RouteDecision(
        target_department=target_department,
        mode=route_mode,  # type: ignore[arg-type]
        requires_rag=need_rag,
        need_rag=need_rag,
        confidence=classification.confidence,
        reason=classification.reason[:240],
        language=classification.language,
        intent=classification.intent,
        router_mode=router_mode,
        router_model=router_model,
        router_fallback_used=router_fallback_used,
        router_error=router_error,
    )


def _extract_json_payload(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _build_ollama_prompt() -> str:
    return (
        "You are a router/classifier only.\n"
        "Do not answer the user's question.\n"
        "Do not decide permissions.\n"
        "Output strict JSON only; no markdown and no extra text.\n"
        "Return exactly keys: language, intent, target_department, need_rag, confidence, reason.\n"
        "language must be one of: zh, en, unknown.\n"
        "intent must be one of: greeting, policy_question, knowledge_lookup, security_test, unsupported.\n"
        "target_department must be one of: tech, sales, marketing, support, hr, admin, product, finance, public, cn, en, unknown.\n"
        "need_rag must be boolean.\n"
        "confidence must be a float between 0 and 1.\n"
        "reason must be short."
    )


def _safe_router_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "ollama_timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return "ollama_http_error"
    if isinstance(exc, httpx.HTTPError):
        return "ollama_unavailable"
    if isinstance(exc, ValidationError):
        return "ollama_invalid_schema"
    if isinstance(exc, json.JSONDecodeError):
        return "ollama_invalid_json"
    return "ollama_router_error"


class BaseLocalModelRouter(ABC):
    @abstractmethod
    def route(self, question: str, mode: AskMode) -> RouteDecision:
        raise NotImplementedError


class RuleBasedLocalModelRouter(BaseLocalModelRouter):
    def route(self, question: str, mode: AskMode) -> RouteDecision:
        classification = _rule_output(question)
        decision = _build_route_decision(
            question=question,
            request_mode=mode,
            classification=classification,
            router_mode="rules",
            router_model="rules",
            router_fallback_used=False,
            router_error=None,
        )
        _router_status_store.update(
            RouterStatus(
                mode="rules",
                model="rules",
                availability="not_checked",
                fallback_used=False,
                error=None,
            )
        )
        return decision


class OllamaQwenRouter(BaseLocalModelRouter):
    def __init__(self, fallback: BaseLocalModelRouter | None = None):
        self._fallback = fallback or RuleBasedLocalModelRouter()

    def route(self, question: str, mode: AskMode) -> RouteDecision:
        try:
            classification = self._classify_with_ollama(question)
            decision = _build_route_decision(
                question=question,
                request_mode=mode,
                classification=classification,
                router_mode="ollama",
                router_model=settings.ollama_router_model,
                router_fallback_used=False,
                router_error=None,
            )
            _router_status_store.update(
                RouterStatus(
                    mode="ollama",
                    model=settings.ollama_router_model,
                    availability="available",
                    fallback_used=False,
                    error=None,
                )
            )
            return decision
        except Exception as exc:
            fallback_error = _safe_router_error(exc)
            fallback_decision = self._fallback.route(question, mode)
            fallback_decision.router_mode = "ollama"
            fallback_decision.router_model = settings.ollama_router_model
            fallback_decision.router_fallback_used = True
            fallback_decision.router_error = fallback_error
            fallback_decision.reason = "Ollama router fallback to deterministic rules."
            _router_status_store.update(
                RouterStatus(
                    mode="ollama",
                    model=settings.ollama_router_model,
                    availability="unavailable",
                    fallback_used=True,
                    error=fallback_error,
                )
            )
            return fallback_decision

    @staticmethod
    def _extract_content(payload: dict) -> str:
        if isinstance(payload.get("choices"), list):
            choices = payload.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
        message = payload.get("message", {})
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        raise ValueError("ollama_invalid_response")

    def _classify_with_ollama(self, question: str) -> OllamaRouterOutput:
        payload = {
            "model": settings.ollama_router_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": _build_ollama_prompt()},
                {"role": "user", "content": question},
            ],
            "options": {"temperature": 0},
        }
        base_url = settings.ollama_base_url.rstrip("/")
        url = f"{base_url}/api/chat"
        with httpx.Client(timeout=settings.ollama_router_timeout_seconds) as client:
            response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            content = self._extract_content(response.json())

        parsed = _extract_json_payload(content)
        if parsed is None:
            raise json.JSONDecodeError("invalid router json", content, 0)
        return OllamaRouterOutput.model_validate(parsed)


def _router_factory() -> BaseLocalModelRouter:
    if settings.local_router_mode == "ollama":
        return OllamaQwenRouter()
    return RuleBasedLocalModelRouter()


router = _router_factory()


def route_question(question: str, mode: AskMode) -> RouteDecision:
    return router.route(question, mode)
