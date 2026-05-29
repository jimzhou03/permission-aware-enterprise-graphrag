from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Literal

import httpx
from pydantic import AliasChoices, BaseModel, Field, ValidationError, model_validator

from app.core.config import get_settings
from app.schemas.qa import AskMode, RouteDecision, RouterIntent, RouterLanguage, RouterMode


settings = get_settings()

DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tech": (
        "tech",
        "sdk",
        "api",
        "deployment",
        "deploy",
        "device pairing",
        "pairing",
        "task dispatch",
        "route planning",
        "telemetry",
        "integration",
        "robot command",
        "技术",
        "部署",
        "设备接入",
        "任务调度",
        "导航",
        "故障排查",
        "故障诊断",
        "机器人故障诊断",
        "日志与遥测",
        "技术工单",
        "现场派单",
    ),
    "sales": (
        "sales",
        "pricing",
        "quote",
        "discount",
        "channel",
        "opportunity",
        "contract quote",
        "销售",
        "报价",
        "折扣",
        "客户分级",
        "渠道",
        "销售话术",
        "商机",
        "合同报价",
    ),
    "marketing": (
        "marketing",
        "brand",
        "expo",
        "campaign",
        "media",
        "materials",
        "市场",
        "品牌",
        "展会",
        "宣传",
        "案例包装",
        "媒体",
        "物料",
    ),
    "support": (
        "support",
        "after-sales",
        "warranty",
        "ticket",
        "escalation",
        "incident handling",
        "客服",
        "售后",
        "保修",
        "工单",
        "故障处理",
        "客户投诉",
        "服务升级",
    ),
    "hr": (
        "hr",
        "hiring",
        "recruit",
        "recruitment",
        "onboarding",
        "attendance",
        "performance",
        "training",
        "probation",
        "payroll",
        "compensation",
        "salary",
        "人事",
        "入职",
        "考勤",
        "绩效",
        "培训",
        "试用期",
        "薪酬",
        "招聘",
        "招人",
        "招聘流程",
    ),
    "admin": (
        "admin",
        "administration",
        "meeting room",
        "procurement",
        "asset",
        "visitor registration",
        "approval",
        "行政",
        "会议室",
        "采购",
        "办公资产",
        "访客登记",
        "行政审批",
    ),
    "product": (
        "product",
        "prd",
        "prototype review",
        "release planning",
        "canary release",
        "production workflow",
        "spec",
        "roadmap",
        "version planning",
        "competitor",
        "feature priority",
        "产品部",
        "产品部门",
        "产品生产流程",
        "prd 编写",
        "原型评审",
        "灰度发布",
        "产品规格",
        "路线图",
        "版本规划",
        "竞品分析",
        "功能优先级",
    ),
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
COMPANY_INFO_KEYWORDS = (
    "company business",
    "what does your company do",
    "what does the company do",
    "company profile",
    "product line",
    "service robot",
    "inspection robot",
    "reception robot",
    "delivery robot",
    "公司业务",
    "公司是做什么的",
    "你们公司是做什么",
    "主营业务",
    "有哪些机器人",
    "产品线",
    "星海智造",
    "服务机器人",
    "巡检机器人",
    "迎宾机器人",
    "配送机器人",
)
BUSINESS_COOPERATION_KEYWORDS = (
    "business cooperation",
    "partnership",
    "contact sales",
    "how to cooperate",
    "商务合作",
    "如何商务合作",
    "如何合作",
    "合作流程",
    "商务对接",
    "商务联系",
)
PUBLIC_POLICY_KEYWORDS = (
    "公开资料",
    "公开介绍",
    "公开售后政策",
    "对外售后政策",
    "官网售后政策",
    "公开服务政策",
    "对外服务政策",
    "公开服务范围",
    "公开售后",
    "对外售后",
    "公开产品",
    "参观须知",
    "联系方式",
    "公开联系方式",
    "官网联系方式",
    "对外合作",
    "visitor guide",
    "public policy",
    "public contact",
    "public service policy",
    "after-sales policy",
)
PUBLIC_POLICY_CONTEXT_KEYWORDS = (
    "公开",
    "对外",
    "官网",
    "official website",
    "public",
)
PUBLIC_SCOPE_EXPLICIT_KEYWORDS = (
    "公司介绍",
    "服务范围",
    "商务合作入口",
    "公开服务政策",
    "公开售后政策",
    "公开资料",
    "公开联系方式",
)
PUBLIC_SERVICE_POLICY_KEYWORDS = (
    "售后政策",
    "服务政策",
    "服务范围",
    "联系方式",
    "after-sales policy",
    "service policy",
    "service scope",
    "public contact",
)
CLARIFICATION_REQUIRED_KEYWORDS = (
    "那个流程",
    "这个流程",
    "那个政策",
    "这个政策",
    "内部流程怎么走",
    "that process",
    "this process",
    "that policy",
    "this policy",
    "which process",
    "which policy",
)
INTERNAL_RISK_KEYWORDS = (
    "内部",
    "internal",
    "权限",
    "access",
    "申请",
    "流程",
    "policy",
    "procedure",
    "制度",
)
SUPPORT_INTERNAL_STRICT_KEYWORDS = (
    "客服内部工单",
    "内部工单",
    "客户投诉明细",
    "售后内部处理流程",
    "support 部门内部知识",
    "support部门内部知识",
    "客服部内部知识",
    "support internal",
)
COMPANY_INTERNAL_KEYWORDS = (
    "公司组织架构",
    "组织架构",
    "部门职责",
    "每个部门负责",
    "跨部门协作",
    "协作流程",
    "内部知识库使用规范",
    "权限申请流程",
    "怎么申请权限",
    "申请权限",
    "公司内部员工",
    "内部权限申请",
    "知识库权限申请",
    "部门权限申请",
    "公司内部员工如何申请知识库权限",
    "内部问题找哪个部门",
    "内部协作",
    "company organization",
    "organization structure",
    "department responsibility",
    "cross department process",
    "cross-functional process",
    "permission request",
    "internal kb policy",
)
ASSISTANT_IDENTITY_KEYWORDS = (
    "who are you",
    "what are you",
    "introduce yourself",
    "你是谁",
    "你是什么",
    "介绍一下你自己",
)
ASSISTANT_CAPABILITY_KEYWORDS = (
    "what can you do",
    "how can you help",
    "capability",
    "你能做什么",
    "你可以做什么",
    "你可以帮我什么",
    "你能回答什么",
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
    "敏感信息",
    "内部资料",
)
GREETING_ZH = {"你好", "您好", "早上好", "晚上好"}
GREETING_EN = {"hello", "hi", "good morning", "good evening"}
KNOWN_DEPARTMENTS = {
    "hr",
    "tech",
    "sales",
    "marketing",
    "support",
    "admin",
    "product",
}
PUBLIC_KB_CODE = "public-policy"
COMPANY_KB_CODE = "company-internal"
DEPARTMENT_TO_KB_CODE = {
    "tech": "tech-internal",
    "sales": "sales-internal",
    "marketing": "marketing-internal",
    "support": "support-internal",
    "hr": "hr-internal",
    "admin": "admin-internal",
    "product": "product-internal",
}


class OllamaRouterOutput(BaseModel):
    query_language: RouterLanguage = Field(validation_alias=AliasChoices("query_language", "language"))
    intent: RouterIntent
    target_department: str = "unknown"
    need_rag: bool = True
    requires_internal_access: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _normalize_fields(self) -> "OllamaRouterOutput":
        if self.intent in {"greeting", "assistant_identity", "assistant_capability", "unsupported"}:
            self.need_rag = False
        if self.intent == "department_internal":
            self.requires_internal_access = True
            if not self.target_department or self.target_department in {"unknown", "public", "company"}:
                self.target_department = "unknown"
        elif self.target_department not in {"unknown", "public", "company"} and self.intent not in {
            "greeting",
            "assistant_identity",
            "assistant_capability",
            "company_intro",
            "business_cooperation",
            "unsupported",
        }:
            self.requires_internal_access = True
        return self


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


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(token in text for token in keywords)


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
    lowered = _normalize_for_greeting(question)
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        if _contains_any(lowered, keywords):
            return department
    return None


def _is_company_internal_question(question: str) -> bool:
    lowered = _normalize_for_greeting(question)
    return _contains_any(lowered, COMPANY_INTERNAL_KEYWORDS)


def _is_explicit_public_policy_question(question: str) -> bool:
    lowered = _normalize_for_greeting(question)
    has_public_context = _contains_any(lowered, PUBLIC_POLICY_CONTEXT_KEYWORDS)
    has_public_policy_topic = _contains_any(lowered, PUBLIC_SERVICE_POLICY_KEYWORDS) or _contains_any(
        lowered, PUBLIC_SCOPE_EXPLICIT_KEYWORDS
    )
    has_public_generic_policy_topic = _contains_any(lowered, POLICY_KEYWORDS)
    has_internal_support_marker = _contains_any(lowered, SUPPORT_INTERNAL_STRICT_KEYWORDS)
    return (
        has_public_context
        and (has_public_policy_topic or has_public_generic_policy_topic)
        and not has_internal_support_marker
    )


def _is_public_question(question: str) -> bool:
    lowered = _normalize_for_greeting(question)
    return (
        _is_explicit_public_policy_question(question)
        or
        _contains_any(lowered, COMPANY_INFO_KEYWORDS)
        or _contains_any(lowered, BUSINESS_COOPERATION_KEYWORDS)
        or _contains_any(lowered, PUBLIC_POLICY_KEYWORDS)
    )


def _is_clarification_required_question(question: str, target_department: str | None) -> bool:
    normalized = _normalize_for_greeting(question)
    if target_department in DEPARTMENT_TO_KB_CODE:
        return False
    if _is_public_question(question):
        return False
    if _is_company_internal_question(question):
        return False
    if _contains_any(normalized, CLARIFICATION_REQUIRED_KEYWORDS):
        return True
    if any(token in normalized for token in ("那个", "这个", "that", "this")) and _contains_any(normalized, POLICY_KEYWORDS):
        return True
    if _contains_any(normalized, ("流程", "政策", "制度", "process", "policy", "procedure")) and len(normalized) <= 14:
        return True
    if _contains_any(normalized, INTERNAL_RISK_KEYWORDS) and not _contains_any(
        normalized, PUBLIC_POLICY_CONTEXT_KEYWORDS
    ):
        if not any(token in normalized for token in ("公司", "company")):
            return True
    return False


def detect_intent(question: str) -> RouterIntent:
    lowered = _normalize_for_greeting(question)
    if is_simple_greeting(question):
        return "greeting"
    if _contains_any(lowered, ASSISTANT_IDENTITY_KEYWORDS):
        return "assistant_identity"
    if _contains_any(lowered, ASSISTANT_CAPABILITY_KEYWORDS):
        return "assistant_capability"
    if any(token in lowered for token in SECURITY_TEST_KEYWORDS):
        return "security_test"
    if _is_explicit_public_policy_question(question):
        return "company_intro"
    if _is_company_internal_question(question):
        return "policy_question"
    if _contains_any(lowered, COMPANY_INFO_KEYWORDS):
        return "company_intro"
    if _contains_any(lowered, BUSINESS_COOPERATION_KEYWORDS):
        return "business_cooperation"
    if _contains_any(lowered, PUBLIC_POLICY_KEYWORDS):
        return "company_intro"
    target_department = detect_target_department(question)
    if target_department is not None:
        return "department_internal"
    if any(token in lowered for token in POLICY_KEYWORDS):
        return "policy_question"
    if len(lowered.strip()) < 2 or re.fullmatch(r"[\W_]+", lowered):
        return "unsupported"
    return "knowledge_lookup"


def _rule_output(question: str) -> OllamaRouterOutput:
    query_language = detect_language(question)
    intent = detect_intent(question)
    department = detect_target_department(question) or "unknown"
    requires_internal_access = intent in {"department_internal", "security_test"} or _is_company_internal_question(question)
    if intent in {"greeting", "assistant_identity", "assistant_capability", "unsupported"}:
        need_rag = False
    else:
        need_rag = True
    if intent in {"greeting", "assistant_identity", "assistant_capability"}:
        confidence = 0.98
    elif intent in {"company_intro", "business_cooperation"}:
        confidence = 0.94
    elif department != "unknown":
        confidence = 0.88
    else:
        confidence = 0.74
    reason = "Rule router classification."
    if query_language == "zh":
        reason = "规则路由分类结果。"
    return OllamaRouterOutput(
        query_language=query_language,
        intent=intent,
        target_department=department,  # type: ignore[arg-type]
        need_rag=need_rag,
        requires_internal_access=requires_internal_access,
        confidence=confidence,
        reason=reason,
    )


def _sanitize_department(value: str, question: str) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")
    alias_map = {
        "technology": "tech",
        "technical": "tech",
        "customer-support": "support",
        "customer service": "support",
        "human-resources": "hr",
        "operations-admin": "admin",
        "operation-admin": "admin",
    }
    normalized = alias_map.get(raw, raw)
    if normalized in KNOWN_DEPARTMENTS:
        return normalized
    detected = detect_target_department(question)
    if detected in KNOWN_DEPARTMENTS:
        return detected
    return None


def _build_target_selection(
    *,
    question: str,
    classification: OllamaRouterOutput,
    target_department: str | None,
    route_mode: str,
) -> tuple[str, str | None, list[str], bool]:
    normalized = _normalize_for_greeting(question)
    raw_target_department = str(classification.target_department or "").strip().lower()

    if route_mode == "unsupported":
        return "unsupported", None, [], False
    if route_mode == "general":
        return "general", None, [], False

    if _is_explicit_public_policy_question(question):
        return "public", None, [PUBLIC_KB_CODE], False

    if _is_company_internal_question(question):
        return "company", None, [COMPANY_KB_CODE], True

    if classification.intent in {"company_intro", "business_cooperation"} or _is_public_question(question):
        return "public", None, [PUBLIC_KB_CODE], False

    if target_department in DEPARTMENT_TO_KB_CODE:
        kb_code = DEPARTMENT_TO_KB_CODE[target_department]
        return "department", target_department, [kb_code], True

    clarification_required = _is_clarification_required_question(question, target_department)

    if classification.intent == "security_test":
        if raw_target_department and raw_target_department not in {"unknown", "public", "company"}:
            return "department", None, [f"{raw_target_department}-internal"], True
        if any(token in normalized for token in ("internal", "内部", "机密", "confidential")):
            return "company", None, [COMPANY_KB_CODE], True
        return "department", None, [], True

    if classification.intent == "policy_question":
        if raw_target_department and raw_target_department not in {"unknown", "public", "company"}:
            return "department", None, [f"{raw_target_department}-internal"], True
        if _is_explicit_public_policy_question(question):
            return "public", None, [PUBLIC_KB_CODE], False
        if clarification_required:
            return "clarification_required", None, [], False
        if _contains_any(normalized, POLICY_KEYWORDS):
            return "company", None, [COMPANY_KB_CODE], True

    if classification.requires_internal_access:
        if raw_target_department and raw_target_department not in {"unknown", "public", "company"}:
            return "department", None, [f"{raw_target_department}-internal"], True
        if clarification_required:
            return "clarification_required", None, [], False
        return "company", None, [COMPANY_KB_CODE], True

    if clarification_required:
        return "clarification_required", None, [], False
    return "public", None, [PUBLIC_KB_CODE], False


def _route_mode_from_inputs(request_mode: AskMode, classification_need_rag: bool, intent: RouterIntent) -> str:
    if request_mode == "graphrag":
        return "graphrag"
    if request_mode == "rag":
        return "rag"
    if intent == "unsupported":
        return "unsupported"
    if intent in {"greeting", "assistant_identity", "assistant_capability"} or not classification_need_rag:
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
    target_scope, scoped_department, target_kb_codes, requires_internal_access = _build_target_selection(
        question=question,
        classification=classification,
        target_department=target_department,
        route_mode=route_mode,
    )
    reason = classification.reason[:240]
    if target_scope == "clarification_required":
        route_mode = "clarification_required"
        need_rag = False
        reason = "Router could not confidently map the query to public, company, or department scope."
    return RouteDecision(
        target_scope=target_scope,  # type: ignore[arg-type]
        target_department=scoped_department,
        target_kb_codes=target_kb_codes,
        mode=route_mode,  # type: ignore[arg-type]
        requires_rag=need_rag,
        need_rag=need_rag,
        confidence=classification.confidence,
        reason=reason,
        language=classification.query_language,
        query_language=classification.query_language,
        requires_internal_access=requires_internal_access,
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
        "Return exactly keys: query_language, intent, target_department, need_rag, requires_internal_access, confidence, reason.\n"
        "query_language must be one of: zh, en, unknown.\n"
        "intent must be one of: greeting, assistant_identity, assistant_capability, company_intro, business_cooperation, policy_question, department_internal, knowledge_lookup, security_test, unsupported.\n"
        "target_department must be one of: tech, sales, marketing, support, hr, admin, product, public, company, unknown.\n"
        "need_rag must be boolean.\n"
        "requires_internal_access must be boolean.\n"
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
