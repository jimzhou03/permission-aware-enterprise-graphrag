from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re

import httpx

from app.core.config import get_settings
from app.schemas.qa import Citation, GraphPath


settings = get_settings()


@dataclass
class GeneratedAnswer:
    answer: str
    model: str


class BaseGeneratorProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate(self, question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
        raise NotImplementedError


def _build_context_block(citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    if not citations:
        return "No authorized citations found."

    lines = []
    for index, citation in enumerate(citations, start=1):
        lines.append(
            f"[{index}] kb={citation.kb_code} doc={citation.document_title} score={citation.score:.4f}\n"
            f"excerpt={citation.excerpt}"
        )

    if graph_paths:
        lines.append("")
        lines.append("Graph Paths:")
        for index, path in enumerate(graph_paths, start=1):
            lines.append(f"({index}) {' -> '.join(path.path)} | {path.explanation}")
    return "\n".join(lines)


def _is_zh_text(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _shorten_excerpt(text: str, limit: int = 140) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _strip_markdown_noise(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = raw_line.strip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = re.sub(r"^`{1,3}", "", line)
        if line:
            lines.append(line)
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _extract_query_terms(question: str) -> set[str]:
    lowered = question.lower()
    en_terms = {token for token in re.findall(r"[a-z]{2,}", lowered) if len(token) >= 3}
    zh_chars = re.findall(r"[\u4e00-\u9fff]", question)
    zh_terms = set()
    for idx in range(len(zh_chars) - 1):
        zh_terms.add("".join(zh_chars[idx : idx + 2]))
    return en_terms | zh_terms


def has_sufficient_retrieval_signal(question: str, citations: list[Citation]) -> bool:
    if not citations:
        return False
    terms = _extract_query_terms(question)
    if not terms:
        return True
    for citation in citations[:4]:
        text = f"{citation.document_title} {_strip_markdown_noise(citation.excerpt).lower()}"
        if any(term in text for term in terms):
            return True
    return max((float(item.score) for item in citations[:4]), default=0.0) >= 0.58


def _first_sentence(text: str, is_zh: bool) -> str:
    separators = r"[。！？]" if is_zh else r"[.!?]"
    parts = re.split(separators, _strip_markdown_noise(text))
    for part in parts:
        candidate = re.sub(r"\s+", " ", part).strip()
        if candidate:
            return candidate
    return _shorten_excerpt(text, limit=100)


def _render_mock_answer(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    is_zh = _is_zh_text(question)
    if not citations or not has_sufficient_retrieval_signal(question, citations):
        if is_zh:
            return "当前授权知识库中没有足够信息回答该问题。"
        return "There is not enough information in the currently authorized knowledge bases to answer this question."

    top_citations = citations[:4]
    key_points = [
        (
            f"{citation.document_title}：{_shorten_excerpt(_strip_markdown_noise(citation.excerpt))}"
            if is_zh
            else f"{citation.document_title}: {_shorten_excerpt(_strip_markdown_noise(citation.excerpt))}"
        )
        for citation in top_citations
    ]
    conclusion = _first_sentence(top_citations[0].excerpt, is_zh)
    if is_zh:
        lines = [
            "根据你当前账号可访问的知识库，整理如下：",
            "",
            f"简短结论：{conclusion}",
            "",
            "关键要点：",
        ]
        for index, point in enumerate(key_points, start=1):
            lines.append(f"{index}. {point}")
        lines.extend(["", "相关来源："])
        for index, citation in enumerate(top_citations, start=1):
            lines.append(f"{index}. {citation.kb_name} / {citation.document_title}")
        lines.extend(["", "权限说明：仅基于当前账号可访问知识库生成，未包含未授权部门内容。"])
    else:
        lines = [
            "Based on the knowledge bases available to your account:",
            "",
            f"Short conclusion: {conclusion}",
            "",
            "Key points:",
        ]
        for index, point in enumerate(key_points, start=1):
            lines.append(f"{index}. {point}")
        lines.extend(["", "Relevant sources:"])
        for index, citation in enumerate(top_citations, start=1):
            lines.append(f"{index}. {citation.kb_name} / {citation.document_title}")
        lines.extend(["", "Access note: this answer is generated only from knowledge bases authorized for your account."])

    if graph_paths:
        lines.append("")
        if is_zh:
            lines.append(f"图谱补充：已参考 {len(graph_paths)} 条授权关系路径。")
        else:
            lines.append(f"Graph note: referenced {len(graph_paths)} authorized relationship paths.")
    return "\n".join(lines)


def _build_messages(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> list[dict[str, str]]:
    context = _build_context_block(citations, graph_paths)
    return [
        {
            "role": "system",
            "content": (
                "You are an enterprise assistant. Use only the provided authorized context. "
                "If context is empty, say no relevant authorized documents were found. "
                "Never invent knowledge outside the provided context."
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nAuthorized Context:\n{context}",
        },
    ]


def _extract_ollama_content(payload: dict) -> str:
    message = payload.get("message", {})
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    if isinstance(payload.get("choices"), list):
        choices = payload.get("choices", [])
        if choices and isinstance(choices[0], dict):
            inner = choices[0].get("message", {})
            if isinstance(inner, dict) and isinstance(inner.get("content"), str):
                return inner["content"]
    raise ValueError("invalid_ollama_llm_response")


def _effective_llm_mode() -> str:
    if settings.llm_mode == "api":
        return "openai-compatible"
    return settings.llm_mode


class MockGeneratorProvider(BaseGeneratorProvider):
    @property
    def model_name(self) -> str:
        return settings.llm_model

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
        return GeneratedAnswer(
            answer=_render_mock_answer(question, citations, graph_paths),
            model=f"mock:{self.model_name}",
        )


class OpenAICompatibleGeneratorProvider(BaseGeneratorProvider):
    @property
    def model_name(self) -> str:
        return settings.llm_model

    @property
    def provider_name(self) -> str:
        return "openai-compatible"

    def generate(self, question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
        payload = {
            "model": self.model_name,
            "temperature": settings.llm_temperature,
            "messages": _build_messages(question, citations, graph_paths),
        }
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"

        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                f"{settings.llm_api_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

        answer = content.strip() or "No relevant authorized documents were found."
        return GeneratedAnswer(answer=answer, model=f"openai-compatible:{self.model_name}")


class OllamaGeneratorProvider(BaseGeneratorProvider):
    @property
    def model_name(self) -> str:
        return settings.llm_ollama_model

    @property
    def provider_name(self) -> str:
        return "ollama"

    def generate(self, question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
        payload = {
            "model": self.model_name,
            "stream": False,
            "messages": _build_messages(question, citations, graph_paths),
            "options": {"temperature": settings.llm_temperature},
        }
        url = f"{settings.llm_ollama_base_url.rstrip('/')}/api/chat"
        with httpx.Client(timeout=settings.llm_ollama_timeout_seconds) as client:
            response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            content = _extract_ollama_content(response.json())

        answer = content.strip() or "No relevant authorized documents were found."
        return GeneratedAnswer(answer=answer, model=f"ollama:{self.model_name}")


def _select_provider() -> BaseGeneratorProvider:
    mode = _effective_llm_mode()
    if mode == "ollama":
        return OllamaGeneratorProvider()
    if mode == "openai-compatible":
        return OpenAICompatibleGeneratorProvider()
    return MockGeneratorProvider()


def generate_answer(question: str, citations: list[Citation], graph_paths: list[GraphPath]) -> GeneratedAnswer:
    provider = _select_provider()
    if provider.provider_name == "mock":
        return provider.generate(question, citations, graph_paths)

    try:
        return provider.generate(question, citations, graph_paths)
    except Exception:
        # Keep service available in local/offline environments; fall back to deterministic mock answer.
        fallback = MockGeneratorProvider()
        generated = fallback.generate(question, citations, graph_paths)
        generated.model = f"mock-fallback:{provider.provider_name}:{provider.model_name}"
        return generated
