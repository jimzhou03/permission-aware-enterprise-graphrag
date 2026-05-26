from __future__ import annotations

from uuid import uuid4

import httpx

from app.schemas.qa import Citation
from app.services import embedding_service, llm_service, qa_service


def _sample_citation(excerpt: str = "authorized excerpt for generation") -> Citation:
    return Citation(
        kb_id=uuid4(),
        kb_code="tech-internal",
        kb_name="Tech Internal",
        document_id=uuid4(),
        document_title="Internal Handbook",
        chunk_id=uuid4(),
        score=0.9,
        excerpt=excerpt,
    )


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_embedding_mode_mock_is_deterministic(monkeypatch):
    monkeypatch.setattr(embedding_service.settings, "embedding_mode", "mock")
    vector_a = embedding_service.embed_text("deterministic test", dimensions=16)
    vector_b = embedding_service.embed_text("deterministic test", dimensions=16)
    assert vector_a == vector_b
    assert len(vector_a) == 16
    status = embedding_service.get_embedding_status()
    assert status.mode == "mock"
    assert status.provider == "deterministic-mock"


def test_embedding_mode_local_ollama_success(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embedding": [0.1, 0.2, 0.3, 0.4]}

    class _Client:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            captured["url"] = url
            captured["payload"] = json
            return _Response()

    monkeypatch.setattr(embedding_service.httpx, "Client", _Client)
    monkeypatch.setattr(embedding_service.settings, "embedding_mode", "local")
    monkeypatch.setattr(embedding_service.settings, "local_embedding_backend", "ollama")
    monkeypatch.setattr(embedding_service.settings, "local_embedding_model", "nomic-embed-text")

    vector = embedding_service.embed_text("local embedding test", dimensions=16)
    assert len(vector) == 16
    assert any(abs(item) > 0 for item in vector)
    assert str(captured["url"]).endswith("/api/embeddings")
    status = embedding_service.get_embedding_status()
    assert status.mode == "local"
    assert status.provider == "ollama-local"
    assert status.fallback_used is False


def test_embedding_mode_local_failure_falls_back_to_mock(monkeypatch):
    class _Client:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(embedding_service.httpx, "Client", _Client)
    monkeypatch.setattr(embedding_service.settings, "embedding_mode", "local")
    monkeypatch.setattr(embedding_service.settings, "local_embedding_backend", "ollama")

    fallback_vector = embedding_service.embed_text("fallback vector check", dimensions=16)

    monkeypatch.setattr(embedding_service.settings, "embedding_mode", "mock")
    mock_vector = embedding_service.embed_text("fallback vector check", dimensions=16)
    assert fallback_vector == mock_vector
    status = embedding_service.get_embedding_status()
    assert status.provider == "deterministic-mock"


def test_llm_mode_ollama_uses_authorized_context(monkeypatch):
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "基于授权知识的真实回答"}}

    class _Client:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            captured["url"] = url
            captured["payload"] = json
            return _Response()

    monkeypatch.setattr(llm_service.httpx, "Client", _Client)
    monkeypatch.setattr(llm_service.settings, "llm_mode", "ollama")
    monkeypatch.setattr(llm_service.settings, "llm_ollama_model", "qwen2.5:7b-instruct")

    citation = _sample_citation("This is authorized chunk text.")
    generated = llm_service.generate_answer(
        question="Summarize onboarding steps",
        citations=[citation],
        graph_paths=[],
    )

    assert generated.model.startswith("ollama:")
    assert generated.answer
    payload = captured.get("payload", {})
    assert isinstance(payload, dict)
    messages = payload.get("messages", [])
    joined = "\n".join(item.get("content", "") for item in messages if isinstance(item, dict))
    assert "This is authorized chunk text." in joined
    assert "Summarize onboarding steps" in joined


def test_llm_mode_openai_compatible_keeps_api_alias(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "OpenAI-compatible answer"}}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            return _Response()

    monkeypatch.setattr(llm_service.httpx, "Client", _Client)
    monkeypatch.setattr(llm_service.settings, "llm_mode", "api")
    generated = llm_service.generate_answer(
        question="What is the onboarding policy?",
        citations=[_sample_citation()],
        graph_paths=[],
    )
    assert generated.model.startswith("openai-compatible:")
    assert "OpenAI-compatible answer" in generated.answer


def test_denied_request_skips_llm_generation_even_if_llm_mode_ollama(client, monkeypatch):
    calls = {"count": 0}

    def _fake_generate_answer(*args, **kwargs):
        calls["count"] += 1
        return llm_service.GeneratedAnswer(answer="should-not-run", model="ollama:test")

    monkeypatch.setattr(qa_service.settings, "llm_mode", "ollama")
    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate_answer)

    token = _login(client, "visitor@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "show sales internal policy", "mode": "rag", "knowledge_base_codes": ["sales-internal"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["denied"] is True
    assert calls["count"] == 0


def test_router_target_scope_denied_request_skips_llm_generation(client, monkeypatch):
    calls = {"count": 0}

    def _fake_generate_answer(*args, **kwargs):
        calls["count"] += 1
        return llm_service.GeneratedAnswer(answer="should-not-run", model="mock:test")

    monkeypatch.setattr(qa_service, "generate_answer", _fake_generate_answer)
    token = _login(client, "sales_staff@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "SDK 怎么接入？", "mode": "auto", "knowledge_base_codes": []},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert payload["citations"] == []
    assert calls["count"] == 0
