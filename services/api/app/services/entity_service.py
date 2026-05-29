from __future__ import annotations

import re
from typing import Literal


EntityType = Literal["Department", "Product", "Workflow", "Policy", "System", "Role", "Unknown"]

STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "used",
    "only",
    "must",
    "into",
    "also",
    "will",
    "have",
    "for",
    "and",
    "the",
    "are",
    "not",
    "can",
    "all",
    "you",
    "your",
    "our",
    "about",
    "what",
    "how",
}

DOMAIN_ENTITY_CATALOG: dict[str, tuple[str, EntityType]] = {
    "tech": ("tech-department", "Department"),
    "sales": ("sales-department", "Department"),
    "marketing": ("marketing-department", "Department"),
    "support": ("support-department", "Department"),
    "hr": ("hr-department", "Department"),
    "admin": ("admin-department", "Department"),
    "product": ("product-department", "Department"),
    "sdk": ("robot-sdk", "System"),
    "api": ("api-integration", "System"),
    "deployment": ("deployment-workflow", "Workflow"),
    "deploy": ("deployment-workflow", "Workflow"),
    "troubleshooting": ("troubleshooting-workflow", "Workflow"),
    "policy": ("policy", "Policy"),
    "procedure": ("procedure", "Workflow"),
    "workflow": ("workflow", "Workflow"),
    "prd": ("product-requirements-document", "Product"),
    "roadmap": ("product-roadmap", "Product"),
    "onboarding": ("onboarding-workflow", "Workflow"),
    "hiring": ("hiring-workflow", "Workflow"),
    "recruitment": ("hiring-workflow", "Workflow"),
    "role": ("role-definition", "Role"),
    "权限": ("access-control-policy", "Policy"),
    "流程": ("workflow", "Workflow"),
    "制度": ("internal-policy", "Policy"),
    "招聘": ("hiring-workflow", "Workflow"),
    "招人": ("hiring-workflow", "Workflow"),
    "绩效": ("performance-policy", "Policy"),
    "产品": ("product-line", "Product"),
    "机器人": ("robot-system", "System"),
}


def _normalize_token(token: str) -> str:
    compact = re.sub(r"\s+", "-", token.strip().lower())
    compact = compact.replace("_", "-")
    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "", compact)
    return compact


def infer_entity_type(name: str) -> EntityType:
    lowered = name.lower()
    if lowered in {"tech", "sales", "marketing", "support", "hr", "admin", "product"}:
        return "Department"
    if any(marker in lowered for marker in ("sdk", "api", "system", "robot")):
        return "System"
    if any(marker in lowered for marker in ("workflow", "process", "procedure", "deploy", "troubleshoot")):
        return "Workflow"
    if any(marker in lowered for marker in ("policy", "rule", "制度", "权限", "绩效")):
        return "Policy"
    if any(marker in lowered for marker in ("prd", "roadmap", "product", "spec")):
        return "Product"
    if any(marker in lowered for marker in ("role", "staff", "admin")):
        return "Role"
    return "Unknown"


def _entity_confidence(raw: str, entity_type: EntityType) -> float:
    if raw in DOMAIN_ENTITY_CATALOG:
        return 0.9
    if entity_type == "Unknown":
        return 0.55
    if len(raw) <= 3:
        return 0.68
    return 0.78


def _english_token_candidates(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())


def _chinese_keyword_candidates(text: str) -> list[str]:
    matched: list[str] = []
    for key in DOMAIN_ENTITY_CATALOG:
        if re.search(r"[\u4e00-\u9fff]", key) and key in text:
            matched.append(key)
    return matched


def build_light_entities(text: str, limit: int = 6) -> list[dict[str, str | float]]:
    entities: list[dict[str, str | float]] = []
    seen: set[str] = set()

    candidates = _chinese_keyword_candidates(text) + _english_token_candidates(text)
    for token in candidates:
        normalized = _normalize_token(token)
        if not normalized:
            continue
        if normalized in STOPWORDS or normalized.isdigit():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)

        canonical, predefined_type = DOMAIN_ENTITY_CATALOG.get(
            token,
            (normalized, infer_entity_type(normalized)),
        )
        entity_type = predefined_type if predefined_type != "Unknown" else infer_entity_type(normalized)
        entities.append(
            {
                "name": token,
                "canonical_name": canonical,
                "entity_type": entity_type,
                "confidence": _entity_confidence(token, entity_type),
                "evidence_text": token,
            }
        )
        if len(entities) >= limit:
            break
    return entities


def extract_entities(text: str, limit: int = 6) -> list[str]:
    return [str(item["name"]) for item in build_light_entities(text, limit=limit)]
