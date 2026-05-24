from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings
from app.schemas.qa import AskMode, RouteDecision


settings = get_settings()

DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": ("finance", "salary", "compensation", "payroll", "reimbursement", "budget", "财务", "薪酬", "报销", "预算"),
    "hr": ("hr", "recruit", "hiring", "leave", "attendance", "招聘", "人事", "请假", "考勤"),
    "tech": ("tech", "deploy", "release", "incident", "service", "技术", "发布", "故障", "运维"),
}

GREETING_ZH = {"你好", "您好", "早上好"}
GREETING_EN = {"hello", "hi", "good morning"}


def detect_target_department(question: str) -> str | None:
    lowered = question.lower()
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            return department
    return None


def _normalize_for_greeting(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_simple_greeting(question: str) -> bool:
    normalized = _normalize_for_greeting(question)
    if not normalized:
        return False
    if normalized in GREETING_EN or normalized in GREETING_ZH:
        return True
    return False


def _build_general_route_decision(question: str) -> RouteDecision:
    normalized = _normalize_for_greeting(question)
    is_zh = bool(re.search(r"[\u4e00-\u9fff]", normalized))
    reason = "Greeting intent detected." if not is_zh else "识别为问候语意图。"
    return RouteDecision(
        target_department=None,
        mode="general",
        requires_rag=False,
        need_rag=False,
        confidence=0.99,
        reason=reason,
    )


def _forced_mode_decision(target_department: str | None, mode: AskMode) -> RouteDecision | None:
    if mode == "graphrag":
        return RouteDecision(
            target_department=target_department,
            mode="graphrag",
            requires_rag=True,
            need_rag=True,
            confidence=0.9 if target_department else 0.7,
            reason="Requester forced graphrag mode.",
        )
    if mode == "rag":
        return RouteDecision(
            target_department=target_department,
            mode="rag",
            requires_rag=True,
            need_rag=True,
            confidence=0.9 if target_department else 0.7,
            reason="Requester forced rag mode.",
        )
    return None


class BaseLocalModelRouter(ABC):
    @abstractmethod
    def route(self, question: str, mode: AskMode) -> RouteDecision:
        raise NotImplementedError


class RuleBasedLocalModelRouter(BaseLocalModelRouter):
    def route(self, question: str, mode: AskMode) -> RouteDecision:
        if is_simple_greeting(question):
            return _build_general_route_decision(question)

        target_department = detect_target_department(question)
        forced = _forced_mode_decision(target_department, mode)
        if forced is not None:
            return forced
        return RouteDecision(
            target_department=target_department,
            mode="rag",
            requires_rag=True,
            need_rag=True,
            confidence=0.86 if target_department else 0.65,
            reason="Auto mode defaults to permission-scoped rag in rule router.",
        )


class OllamaQwenRouter(BaseLocalModelRouter):
    def __init__(self, fallback: BaseLocalModelRouter | None = None):
        self._fallback = fallback or RuleBasedLocalModelRouter()

    def route(self, question: str, mode: AskMode) -> RouteDecision:
        if is_simple_greeting(question):
            return _build_general_route_decision(question)

        target_department = detect_target_department(question)
        forced = _forced_mode_decision(target_department, mode)
        if forced is not None:
            return forced

        payload = {
            "model": settings.local_router_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a local intent router. "
                        "Return strict JSON only with keys: mode, target_department, requires_rag, confidence, reason. "
                        "Allowed mode values: rag, graphrag, direct. "
                        "Allowed target_department values: hr, finance, tech, public, null."
                    ),
                },
                {"role": "user", "content": question},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if settings.local_router_api_key:
            headers["Authorization"] = f"Bearer {settings.local_router_api_key}"

        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(
                    f"{settings.local_router_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            decision = self._parse_model_output(content, question)
            if decision is not None:
                return decision
        except Exception:
            pass

        fallback_decision = self._fallback.route(question, "auto")
        fallback_decision.reason = (
            "Local model router fallback to rules due to unavailable local endpoint or invalid output."
        )
        return fallback_decision

    @staticmethod
    def _parse_model_output(content: str, question: str) -> RouteDecision | None:
        parsed: dict | None = None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    parsed = None
        if not parsed:
            return None

        mode_value = str(parsed.get("mode", "rag")).strip().lower()
        if mode_value not in {"direct", "rag", "graphrag", "general"}:
            mode_value = "rag"
        if mode_value == "direct":
            mode_value = "rag"

        target_department = parsed.get("target_department")
        if target_department is not None:
            target_department = str(target_department).strip().lower()
            if target_department not in {"hr", "finance", "tech", "public"}:
                target_department = detect_target_department(question)

        requires_rag = bool(parsed.get("requires_rag", mode_value in {"rag", "graphrag"}))
        need_rag = bool(parsed.get("need_rag", requires_rag))
        confidence_raw = parsed.get("confidence", 0.7)
        try:
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except (TypeError, ValueError):
            confidence = 0.7
        reason = str(parsed.get("reason", "Local router decision from ollama."))[:240]

        return RouteDecision(
            target_department=target_department,
            mode=mode_value,  # type: ignore[arg-type]
            requires_rag=requires_rag,
            need_rag=need_rag,
            confidence=confidence,
            reason=reason,
        )


def _router_factory() -> BaseLocalModelRouter:
    if settings.local_router_mode == "ollama":
        return OllamaQwenRouter()
    return RuleBasedLocalModelRouter()


router = _router_factory()


def route_question(question: str, mode: AskMode) -> RouteDecision:
    return router.route(question, mode)
