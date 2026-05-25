import pytest
from sqlalchemy import select

from app.core import database as db_module
from app.models import Permission, Role, RolePermission


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _grant_role_permission(role_name: str, permission_code: str) -> None:
    db = db_module.SessionLocal()
    try:
        role = db.scalar(select(Role).where(Role.name == role_name))
        permission = db.scalar(select(Permission).where(Permission.code == permission_code))
        assert role is not None
        assert permission is not None
        existing = db.scalar(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        )
        if existing is None:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            db.commit()
    finally:
        db.close()


@pytest.mark.parametrize(
    ("email", "expected_codes"),
    [
        ("cn_staff@example.local", {"cn-public", "cn-internal"}),
        ("en_staff@example.local", {"en-public", "en-internal"}),
        ("visitor@example.local", {"public-policy"}),
        (
            "bilingual_admin@example.local",
            {"cn-public", "cn-internal", "en-public", "en-internal", "public-policy"},
        ),
    ],
)
def test_v018_knowledge_base_scope_matrix(client, email: str, expected_codes: set[str]):
    token = _login(client, email)
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert {item["code"] for item in payload} == expected_codes
    assert all("language" in item and "display_name" in item for item in payload)


def test_document_and_chunk_access_scope_enforced(client):
    cn_token = _login(client, "cn_staff@example.local")
    visitor_token = _login(client, "visitor@example.local")

    cn_kb_response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {cn_token}"})
    assert cn_kb_response.status_code == 200, cn_kb_response.text
    cn_kbs = cn_kb_response.json()
    cn_internal = next(item for item in cn_kbs if item["code"] == "cn-internal")

    cn_docs_response = client.get(
        f"/api/v1/knowledge-bases/{cn_internal['id']}/documents",
        headers={"Authorization": f"Bearer {cn_token}"},
    )
    assert cn_docs_response.status_code == 200, cn_docs_response.text
    cn_docs = cn_docs_response.json()
    assert cn_docs
    protected_doc_id = cn_docs[0]["id"]

    forbidden_docs_response = client.get(
        f"/api/v1/knowledge-bases/{cn_internal['id']}/documents",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert forbidden_docs_response.status_code == 403, forbidden_docs_response.text

    forbidden_chunks_response = client.get(
        f"/api/v1/documents/{protected_doc_id}/chunks",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert forbidden_chunks_response.status_code == 403, forbidden_chunks_response.text

    visitor_kb_response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {visitor_token}"})
    assert visitor_kb_response.status_code == 200, visitor_kb_response.text
    visitor_kb = visitor_kb_response.json()[0]

    visitor_docs_response = client.get(
        f"/api/v1/knowledge-bases/{visitor_kb['id']}/documents",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert visitor_docs_response.status_code == 200, visitor_docs_response.text
    visitor_docs = visitor_docs_response.json()
    assert visitor_docs

    visitor_chunks_response = client.get(
        f"/api/v1/documents/{visitor_docs[0]['id']}/chunks",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert visitor_chunks_response.status_code == 200, visitor_chunks_response.text
    for item in visitor_chunks_response.json():
        assert item["knowledge_base_code"] == "public-policy"


def test_trace_endpoint_filters_chunk_content_for_unauthorized_audit_reader(client):
    cn_token = _login(client, "cn_staff@example.local")
    visitor_token = _login(client, "visitor@example.local")

    ask_response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {cn_token}"},
        json={"question": "请总结中文内部手册里的接入流程和协作约定。", "mode": "rag", "knowledge_base_codes": []},
    )
    assert ask_response.status_code == 200, ask_response.text
    ask_payload = ask_response.json()
    assert ask_payload["citations"]
    request_id = ask_payload["request_id"]

    _grant_role_permission("visitor", "audit:read")
    trace_response = client.get(
        f"/api/v1/qa/{request_id}/trace",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert trace_response.status_code == 200, trace_response.text
    trace_payload = trace_response.json()
    assert trace_payload["request_id"] == request_id
    assert trace_payload["hit_chunk_ids"]
    assert trace_payload["retrieved_chunks"] == []
    assert any("omitted" in item for item in trace_payload["trace_limits"])
    assert set(trace_payload["allowed_kb_codes"]) == {"cn-public", "cn-internal"}
    assert trace_payload["router_mode"] in {"rules", "ollama"}
    assert trace_payload["router_model"]
    assert trace_payload["router_availability"] in {"available", "unavailable", "not_checked"}
    assert isinstance(trace_payload["router_fallback_used"], bool)
    assert trace_payload["router_decision"] is not None
    assert "need_rag" in trace_payload["router_decision"]
    assert [item["tool_name"] for item in trace_payload["function_trace"]] == [
        "classify_query",
        "resolve_user_permission_scope",
        "check_cache",
        "search_allowed_chunks",
        "get_graph_paths",
        "generate_answer",
        "save_audit_log",
    ]


def test_retrieval_config_endpoint_reports_mock_mvp_runtime(client):
    token = _login(client, "cn_staff@example.local")
    response = client.get(
        "/api/v1/system/retrieval-config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["embedding_provider"] == "deterministic-mock"
    assert payload["retrieval_engine"] == "python_cosine_fallback"
    assert payload["top_k"] == payload["default_top_k"] == 5
    assert payload["pgvector_available"] is False
    assert payload["sql_vector_search_enabled"] is False
    assert payload["pgvector_sql_retrieval_enabled"] is False
    assert payload["generator_mode"] == "mock"
    assert payload["router_mode"] == "rules"
    assert payload["router_model"] == "rules"
    assert payload["router_availability"] == "not_checked"
    assert payload["router_fallback_last"] is False
    assert payload["function_calling_mode"] == "backend-controlled-trace"
    assert payload["llm_autonomous_tool_calling"] is False
    assert payload["permission_authority"] == "backend-rbac"
