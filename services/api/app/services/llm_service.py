from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.schemas.qa import Citation, GraphPath


settings = get_settings()


@dataclass
class GeneratedAnswer:
    answer: str
    model: str


def _build_context_block(citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    if not citations:
        return "No authorized citations found."

    lines = []
    for idx, citation in enumerate(citations, start=1):
        lines.append(
            f"[{idx}] kb={citation.kb_code} doc={citation.document_title} score={citation.score:.4f}\n"
            f"excerpt={citation.excerpt}"
        )

    if graph_paths:
        lines.append("")
        lines.append("Graph Paths:")
        for idx, path in enumerate(graph_paths, start=1):
            lines.append(f"({idx}) {' -> '.join(path.path)} | {path.explanation}")
    return "\n".join(lines)


def _render_mock_answer(citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    if not citations:
        return "No relevant authorized documents were found."

    lines = ["Authorized answer generated from the following scoped knowledge:"]
    for idx, citation in enumerate(citations, start=1):
        lines.append(f"{idx}. [{citation.kb_code}] {citation.document_title}: {citation.excerpt}")

    if graph_paths:
        lines.append("")
        lines.append("Graph evidence paths:")
        for idx, path in enumerate(graph_paths, start=1):
            lines.append(f"{idx}. {' -> '.join(path.path)}")
    return "\n".join(lines)


def _build_messages(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> list[dict[str, str]]:
    context = _build_context_block(citations, graph_paths)
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise assistant. Use only the provided authorized context. "
                "If context is empty, say no relevant authorized documents were found. "
                "Do not invent knowledge outside the context."
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nAuthorized Context:\n{context}",
        },
    ]


def _call_openai_compatible(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": _build_messages(question, citations, graph_paths),
    }
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{settings.llm_api_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

    answer = content.strip() or "No relevant authorized documents were found."
    return GeneratedAnswer(answer=answer, model=f"api:{settings.llm_model}")


def generate_answer(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
    if settings.llm_mode != "api":
        return GeneratedAnswer(answer=_render_mock_answer(citations, graph_paths), model=f"mock:{settings.llm_model}")

    try:
        return _call_openai_compatible(question, citations, graph_paths)
    except Exception:
        # Keep service available in local/offline environment; fall back to deterministic mock answer.
        return GeneratedAnswer(
            answer=_render_mock_answer(citations, graph_paths),
            model=f"mock-fallback:{settings.llm_model}",
        )
