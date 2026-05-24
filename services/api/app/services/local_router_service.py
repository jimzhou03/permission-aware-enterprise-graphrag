from __future__ import annotations

from app.schemas.qa import AskMode, RouteDecision


DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": ("finance", "salary", "compensation", "payroll", "reimbursement", "budget", "财务", "薪酬", "报销", "预算"),
    "hr": ("hr", "recruit", "hiring", "leave", "attendance", "招聘", "人事", "请假", "考勤"),
    "tech": ("tech", "deploy", "release", "incident", "service", "技术", "发布", "故障", "运维"),
}


def detect_target_department(question: str) -> str | None:
    lowered = question.lower()
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        if any(word in lowered for word in keywords):
            return department
    return None


def route_question(question: str, mode: AskMode) -> RouteDecision:
    target_department = detect_target_department(question)
    if mode == "graphrag":
        return RouteDecision(
            target_department=target_department,
            mode="graphrag",
            requires_rag=True,
            confidence=0.9 if target_department else 0.7,
            reason="Requester forced graphrag mode.",
        )
    if mode == "rag":
        return RouteDecision(
            target_department=target_department,
            mode="rag",
            requires_rag=True,
            confidence=0.9 if target_department else 0.7,
            reason="Requester forced rag mode.",
        )
    return RouteDecision(
        target_department=target_department,
        mode="rag",
        requires_rag=True,
        confidence=0.86 if target_department else 0.65,
        reason="Auto mode defaults to permission-scoped rag in phase 2.",
    )

