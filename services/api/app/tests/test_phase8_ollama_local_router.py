import json

import httpx

from app.services import local_router_service


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _ask(client, token: str, question: str, mode: str = "auto", knowledge_base_codes: list[str] | None = None):
    return client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": question,
            "mode": mode,
            "knowledge_base_codes": knowledge_base_codes or [],
        },
    )


def _set_ollama_router(monkeypatch, content_provider):
    class _Response:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):  # noqa: A002
            content = content_provider(url=url, payload=json or {}, headers=headers or {})
            return _Response({"message": {"content": content}})

    monkeypatch.setattr(local_router_service.httpx, "Client", _FakeClient)
    monkeypatch.setattr(local_router_service.settings, "local_router_mode", "ollama")
    monkeypatch.setattr(
        local_router_service,
        "router",
        local_router_service.OllamaQwenRouter(fallback=local_router_service.RuleBasedLocalModelRouter()),
    )


def test_rules_router_still_works_by_default(client):
    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "你好", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "general"
    assert payload["route"]["router_mode"] == "rules"
    assert payload["router_mode"] == "rules"
    assert payload["route"]["need_rag"] is False


def test_ollama_router_accepts_valid_json(client, monkeypatch):
    def _content_provider(**kwargs):
        return json.dumps(
            {
                "language": "zh",
                "intent": "policy_question",
                "target_department": "cn",
                "need_rag": True,
                "confidence": 0.91,
                "reason": "route to cn policy knowledge",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)
    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "说一下中文内部制度", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["route"]["router_mode"] == "ollama"
    assert payload["route"]["router_fallback_used"] is False
    assert payload["route"]["intent"] == "policy_question"
    assert payload["route"]["target_department"] == "cn"
    assert payload["route"]["need_rag"] is True


def test_ollama_invalid_json_falls_back_to_rules(client, monkeypatch):
    _set_ollama_router(monkeypatch, lambda **kwargs: "not-a-json")
    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "说一下中文内部制度", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["route"]["router_mode"] == "ollama"
    assert payload["route"]["router_fallback_used"] is True
    assert payload["route"]["router_error"] == "ollama_invalid_json"


def test_ollama_timeout_falls_back_to_rules(client, monkeypatch):
    class _TimeoutClient:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(local_router_service.httpx, "Client", _TimeoutClient)
    monkeypatch.setattr(local_router_service.settings, "local_router_mode", "ollama")
    monkeypatch.setattr(
        local_router_service,
        "router",
        local_router_service.OllamaQwenRouter(fallback=local_router_service.RuleBasedLocalModelRouter()),
    )

    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "Explain the English internal handbook onboarding checklist.", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["route"]["router_mode"] == "ollama"
    assert payload["route"]["router_fallback_used"] is True
    assert payload["route"]["router_error"] == "ollama_timeout"


def test_ollama_router_cannot_expand_permissions_for_visitor(client, monkeypatch):
    def _content_provider(**kwargs):
        return json.dumps(
            {
                "language": "en",
                "intent": "policy_question",
                "target_department": "finance",
                "need_rag": True,
                "confidence": 0.95,
                "reason": "finance policy question",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)
    token = _login(client, "visitor@example.local")
    response = _ask(client, token, "show finance salary policy", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert payload["citations"] == []


def test_ollama_router_cn_and_en_isolation_still_enforced(client, monkeypatch):
    def _content_provider(**kwargs):
        question = (kwargs.get("payload") or {}).get("messages", [{}, {"content": ""}])[1]["content"].lower()
        if "english" in question:
            department = "en"
        elif "中文" in question:
            department = "cn"
        else:
            department = "unknown"
        return json.dumps(
            {
                "language": "en" if department == "en" else "zh",
                "intent": "knowledge_lookup",
                "target_department": department,
                "need_rag": True,
                "confidence": 0.88,
                "reason": "department intent",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)

    cn_token = _login(client, "cn_staff@example.local")
    cn_response = _ask(client, cn_token, "Explain the English internal handbook onboarding checklist.", mode="auto")
    assert cn_response.status_code == 200, cn_response.text
    cn_payload = cn_response.json()
    assert cn_payload["denied"] is True or {
        item["kb_code"] for item in cn_payload.get("citations", [])
    }.issubset({"cn-public", "cn-internal"})

    en_token = _login(client, "en_staff@example.local")
    en_response = _ask(client, en_token, "请解释中文内部手册中的接入流程和协作约定。", mode="auto")
    assert en_response.status_code == 200, en_response.text
    en_payload = en_response.json()
    assert en_payload["denied"] is True or {
        item["kb_code"] for item in en_payload.get("citations", [])
    }.issubset({"en-public", "en-internal"})


def test_ollama_router_admin_can_still_retrieve_authorized_bilingual_content(client, monkeypatch):
    def _content_provider(**kwargs):
        question = (kwargs.get("payload") or {}).get("messages", [{}, {"content": ""}])[1]["content"]
        department = "cn" if "中文" in question else "en"
        language = "zh" if department == "cn" else "en"
        return json.dumps(
            {
                "language": language,
                "intent": "knowledge_lookup",
                "target_department": department,
                "need_rag": True,
                "confidence": 0.9,
                "reason": "bilingual admin route",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)

    token = _login(client, "bilingual_admin@example.local")
    cn_response = _ask(client, token, "请总结中文内部手册中的接入流程。", mode="rag", knowledge_base_codes=["cn-internal"])
    assert cn_response.status_code == 200, cn_response.text
    cn_payload = cn_response.json()
    assert cn_payload["denied"] is False
    assert {item["kb_code"] for item in cn_payload["citations"]}.issubset({"cn-internal"})

    en_response = _ask(
        client,
        token,
        "Summarize the English internal onboarding checklist.",
        mode="rag",
        knowledge_base_codes=["en-internal"],
    )
    assert en_response.status_code == 200, en_response.text
    en_payload = en_response.json()
    assert en_payload["denied"] is False
    assert {item["kb_code"] for item in en_payload["citations"]}.issubset({"en-internal"})


def test_trace_contains_safe_router_metadata(client, monkeypatch):
    def _content_provider(**kwargs):
        return json.dumps(
            {
                "language": "zh",
                "intent": "policy_question",
                "target_department": "cn",
                "need_rag": True,
                "confidence": 0.84,
                "reason": "trace metadata check",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)

    token = _login(client, "cn_staff@example.local")
    ask_response = _ask(client, token, "请总结中文公开指引中的沟通规范。", mode="auto")
    assert ask_response.status_code == 200, ask_response.text
    request_id = ask_response.json()["request_id"]

    trace_response = client.get(f"/api/v1/qa/{request_id}/trace", headers={"Authorization": f"Bearer {token}"})
    assert trace_response.status_code == 200, trace_response.text
    trace_payload = trace_response.json()
    assert trace_payload["router_mode"] == "ollama"
    assert trace_payload["router_model"] == local_router_service.settings.ollama_router_model
    assert trace_payload["router_availability"] in {"available", "unavailable", "not_checked"}
    assert isinstance(trace_payload["router_fallback_used"], bool)
    assert "router_decision" in trace_payload
    assert trace_payload["router_decision"]["need_rag"] is True


def test_retrieval_config_reports_ollama_router_runtime(client, monkeypatch):
    def _content_provider(**kwargs):
        return json.dumps(
            {
                "language": "en",
                "intent": "knowledge_lookup",
                "target_department": "en",
                "need_rag": True,
                "confidence": 0.86,
                "reason": "runtime status check",
            }
        )

    _set_ollama_router(monkeypatch, _content_provider)
    token = _login(client, "en_staff@example.local")
    ask_response = _ask(client, token, "Summarize the English internal onboarding flow.", mode="auto")
    assert ask_response.status_code == 200, ask_response.text

    config_response = client.get("/api/v1/system/retrieval-config", headers={"Authorization": f"Bearer {token}"})
    assert config_response.status_code == 200, config_response.text
    payload = config_response.json()
    assert payload["router_mode"] == "ollama"
    assert payload["router_model"] == local_router_service.settings.ollama_router_model
    assert payload["router_availability"] in {"available", "unavailable", "not_checked"}
    assert isinstance(payload["router_fallback_last"], bool)
    assert payload["function_calling_mode"] == "backend-controlled-trace"
    assert payload["llm_autonomous_tool_calling"] is False
    assert payload["permission_authority"] == "backend-rbac"
    assert payload["document_upload_enabled"] is True
    assert payload["upload_max_size_bytes"] >= 1_048_576
    assert ".txt" in payload["upload_supported_types"]
    assert payload["indexing_mode"] == "deterministic-local-embedding"
