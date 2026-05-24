from __future__ import annotations

import re


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
}


def extract_entities(text: str, limit: int = 6) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    entities: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)
        entities.append(token)
        if len(entities) >= limit:
            break
    return entities

