from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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


def _render_mock_answer(citations: list[Citation], graph_paths: list[GraphPath]) -> str:
    if not citations:
        return "No relevant authorized documents were found."

    lines = ["Authorized answer generated from the following scoped knowledge:"]
    for index, citation in enumerate(citations, start=1):
        lines.append(f"{index}. [{citation.kb_code}] {citation.document_title}: {citation.excerpt}")

    if graph_paths:
        lines.append("")
        lines.append("Graph evidence paths:")
        for index, path in enumerate(graph_paths, start=1):
            lines.append(f"{index}. {' -> '.join(path.path)}")
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
        return GeneratedAnswer(answer=_render_mock_answer(citations, graph_paths), model=f"mock:{self.model_name}")


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

