import json
from uuid import uuid4

import pytest

from app.services import local_router_service


TRACE_ORDER = [
    "classify_query",
    "resolve_user_permission_scope",
    "check_cache",
    "search_allowed_chunks",
    "get_graph_paths",
    "generate_answer",
    "save_audit_log",
]


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


def _trace(client, token: str, request_id: str) -> dict:
    response = client.get(
        f"/api/v1/qa/{request_id}/trace",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _trace_step_map(trace_payload: dict) -> dict[str, dict]:
    steps = trace_payload.get("function_trace", [])
    return {item["tool_name"]: item for item in steps}


def _assert_trace_order(trace_payload: dict) -> None:
    names = [item["tool_name"] for item in trace_payload.get("function_trace", [])]
    assert names == TRACE_ORDER


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


def test_authorized_rag_question_exposes_controlled_function_trace(client):
    token = _login(client, "sales_staff@example.local")
    ask_response = _ask(client, token, "请总结销售部内部报价流程和沟通约定。", mode="rag")
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()
    assert ask_payload["denied"] is False
    assert ask_payload["function_trace_summary"]

    trace_payload = _trace(client, token, ask_payload["request_id"])
    _assert_trace_order(trace_payload)
    steps = _trace_step_map(trace_payload)
    assert steps["classify_query"]["status"] == "success"
    assert steps["resolve_user_permission_scope"]["status"] == "success"
    assert steps["check_cache"]["status"] == "success"
    assert "cache_hit=false" in steps["check_cache"]["output_summary"]
    assert steps["search_allowed_chunks"]["status"] == "success"
    assert steps["generate_answer"]["status"] == "success"
    assert steps["save_audit_log"]["status"] == "success"


def test_general_greeting_trace_skips_retrieval(client):
    token = _login(client, "sales_staff@example.local")
    ask_response = _ask(client, token, "你好", mode="auto")
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()
    assert ask_payload["mode"] == "general"

    trace_payload = _trace(client, token, ask_payload["request_id"])
    _assert_trace_order(trace_payload)
    steps = _trace_step_map(trace_payload)
    assert steps["search_allowed_chunks"]["status"] == "skipped"
    assert steps["get_graph_paths"]["status"] == "skipped"
    assert steps["generate_answer"]["status"] == "success"
    assert trace_payload["retrieved_chunks"] == []


def test_cache_hit_trace_marks_retrieval_and_generation_skipped(client):
    token = _login(client, "sales_staff@example.local")
    question = f"请总结公开资料缓存链路测试 {uuid4().hex}"
    first = _ask(client, token, question, mode="rag")
    assert first.status_code == 200, first.text
    assert first.json()["cache_hit"] is False

    second = _ask(client, token, question, mode="rag")
    assert second.status_code == 200, second.text
    second_payload = second.json()
    assert second_payload["cache_hit"] is True

    trace_payload = _trace(client, token, second_payload["request_id"])
    _assert_trace_order(trace_payload)
    steps = _trace_step_map(trace_payload)
    assert steps["check_cache"]["status"] == "success"
    assert "cache_hit=true" in steps["check_cache"]["output_summary"]
    assert steps["search_allowed_chunks"]["status"] == "skipped"
    assert "cache_hit" in steps["search_allowed_chunks"]["output_summary"]
    assert steps["generate_answer"]["status"] == "skipped"
    assert steps["generate_answer"]["output_summary"] == "cached_answer"


def test_permission_denial_trace_hides_unauthorized_chunk_content(client):
    token = _login(client, "visitor@example.local")
    ask_response = _ask(client, token, "show sales internal policy", mode="rag", knowledge_base_codes=["sales-internal"])
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()
    assert ask_payload["denied"] is True
    assert ask_payload["citations"] == []

    trace_payload = _trace(client, token, ask_payload["request_id"])
    _assert_trace_order(trace_payload)
    steps = _trace_step_map(trace_payload)
    assert steps["search_allowed_chunks"]["status"] == "denied"
    assert steps["generate_answer"]["status"] == "skipped"
    assert trace_payload["retrieved_chunks"] == []
    assert trace_payload["hit_chunk_ids"] == []
    assert all("sales-internal" not in item["output_summary"] for item in trace_payload["function_trace"])


@pytest.mark.parametrize(
    ("email", "question", "expected_allowed_codes"),
    [
        (
            "sales_staff@example.local",
            "Explain the tech internal SDK deployment checklist.",
            {"public-policy", "sales-internal"},
        ),
        (
            "tech_staff@example.local",
            "请解释销售部报价策略与客户沟通话术。",
            {"public-policy", "tech-internal"},
        ),
    ],
)
def test_cross_department_isolation_still_enforced_with_function_trace(
    client,
    email: str,
    question: str,
    expected_allowed_codes: set[str],
):
    token = _login(client, email)
    ask_response = _ask(client, token, question, mode="auto")
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()

    trace_payload = _trace(client, token, ask_payload["request_id"])
    _assert_trace_order(trace_payload)
    assert set(trace_payload["allowed_kb_codes"]) == expected_allowed_codes
    if ask_payload["denied"] is False:
        assert {item["kb_code"] for item in trace_payload["retrieved_chunks"]}.issubset(expected_allowed_codes)


def test_bilingual_admin_can_retrieve_cn_and_en_with_function_trace(client):
    token = _login(client, "bilingual_admin@example.local")

    cn_response = _ask(
        client,
        token,
        "请总结销售部内部报价流程。",
        mode="rag",
        knowledge_base_codes=["sales-internal"],
    )
    assert cn_response.status_code == 200, cn_response.text
    cn_payload = cn_response.json()
    assert cn_payload["denied"] is False
    cn_trace = _trace(client, token, cn_payload["request_id"])
    cn_steps = _trace_step_map(cn_trace)
    assert cn_steps["search_allowed_chunks"]["status"] == "success"
    assert {item["kb_code"] for item in cn_trace["retrieved_chunks"]}.issubset({"sales-internal"})

    en_response = _ask(
        client,
        token,
        "Summarize the tech internal deployment troubleshooting checklist.",
        mode="rag",
        knowledge_base_codes=["tech-internal"],
    )
    assert en_response.status_code == 200, en_response.text
    en_payload = en_response.json()
    assert en_payload["denied"] is False
    en_trace = _trace(client, token, en_payload["request_id"])
    en_steps = _trace_step_map(en_trace)
    assert en_steps["search_allowed_chunks"]["status"] == "success"
    assert {item["kb_code"] for item in en_trace["retrieved_chunks"]}.issubset({"tech-internal"})


def test_frontend_scope_selection_cannot_expand_permissions_in_function_trace(client):
    token = _login(client, "sales_staff@example.local")
    ask_response = _ask(
        client,
        token,
        "show tech internal policy",
        mode="rag",
        knowledge_base_codes=["tech-internal"],
    )
    assert ask_response.status_code == 200, ask_response.text
    payload = ask_response.json()
    assert payload["denied"] is True

    trace_payload = _trace(client, token, payload["request_id"])
    _assert_trace_order(trace_payload)
    assert set(trace_payload["allowed_kb_codes"]) == {"public-policy", "sales-internal"}
    assert trace_payload["retrieved_chunks"] == []
    assert _trace_step_map(trace_payload)["search_allowed_chunks"]["status"] == "denied"


def test_ollama_router_cannot_expand_permissions_in_function_trace(client, monkeypatch):
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
    ask_response = _ask(client, token, "show finance salary policy", mode="auto")
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()
    assert ask_payload["denied"] is True
    assert ask_payload["citations"] == []

    trace_payload = _trace(client, token, ask_payload["request_id"])
    _assert_trace_order(trace_payload)
    steps = _trace_step_map(trace_payload)
    assert set(trace_payload["allowed_kb_codes"]) == {"public-policy"}
    assert trace_payload["retrieved_chunks"] == []
    assert steps["search_allowed_chunks"]["status"] == "denied"
    assert steps["generate_answer"]["status"] == "skipped"
