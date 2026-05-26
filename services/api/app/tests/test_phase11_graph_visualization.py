from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core import database as db_module
from app.core.config import ROOT_DIR
from app.models import Permission, Role, RolePermission
from app.services.graph_service import neo4j_service


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _ask(
    client,
    token: str,
    question: str,
    mode: str = "graphrag",
    knowledge_base_codes: list[str] | None = None,
) -> dict:
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": question, "mode": mode, "knowledge_base_codes": knowledge_base_codes or []},
    )
    assert response.status_code == 200, response.text
    return response.json()


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


def _kb_codes_from_overview(payload: dict) -> set[str]:
    return {item["kb_code"] for item in payload["nodes"] if item.get("type") == "knowledge_base" and item.get("kb_code")}


def test_zh_navigation_labels_localized():
    i18n_path = Path(ROOT_DIR) / "apps" / "web" / "src" / "i18n.ts"
    if not i18n_path.exists():
        pytest.skip(f"frontend localization source is not mounted in this runtime: {i18n_path}")
    content = i18n_path.read_text(encoding="utf-8")
    assert 'navKnowledgeChat: "知识问答"' in content
    assert 'navKnowledgeBases: "知识库"' in content
    assert 'navAuditLogs: "审计日志"' in content
    assert 'navSystemStatus: "系统状态"' in content
    assert 'navDeveloperTrace: "开发者追踪"' in content
    assert 'navGraphRag: "GraphRAG图谱"' in content
    assert 'uploadDocumentAction: "文档上传"' in content
    assert 'documentsPanelTitle: "文档查看器"' in content
    assert 'chunkViewerTitle: "分块查看器"' in content
    assert 'functionTraceTitle: "函数调用追踪"' in content
    assert 'graphTraceTitle: "GraphRAG追踪"' in content


def test_graph_status_endpoint_returns_safe_runtime_status(client):
    token = _login(client, "sales_staff@example.local")
    response = client.get("/api/v1/graph/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload["neo4j_configured"], bool)
    assert isinstance(payload["neo4j_available"], bool)
    assert isinstance(payload["graph_sync_enabled"], bool)
    assert isinstance(payload["graph_sync_needed"], bool)
    assert isinstance(payload["fallback_mode"], str)
    assert "neo4j_password" not in str(payload).lower()


@pytest.mark.parametrize(
    ("email", "expected_codes"),
    [
        ("visitor@example.local", {"public-policy"}),
        ("sales_staff@example.local", {"public-policy", "sales-internal"}),
        ("tech_staff@example.local", {"public-policy", "tech-internal"}),
        (
            "bilingual_admin@example.local",
            {
                "public-policy",
                "tech-internal",
                "sales-internal",
                "marketing-internal",
                "support-internal",
                "hr-internal",
                "admin-internal",
                "product-internal",
            },
        ),
    ],
)
def test_graph_overview_scope_matches_backend_allowed_kbs(client, email: str, expected_codes: set[str]):
    token = _login(client, email)
    response = client.get("/api/v1/graph/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload["allowed_kb_codes"]) == expected_codes
    assert _kb_codes_from_overview(payload).issubset(expected_codes)
    assert all("content=" not in (node.get("metadata_summary") or "") for node in payload["nodes"])


def test_unauthorized_graph_trace_viewer_cannot_see_internal_nodes(client):
    cn_token = _login(client, "sales_staff@example.local")
    visitor_token = _login(client, "visitor@example.local")
    ask_payload = _ask(
        client,
        cn_token,
        f"请总结销售内部制度图谱路径 {uuid4().hex}",
        mode="graphrag",
        knowledge_base_codes=["sales-internal"],
    )
    assert ask_payload["denied"] is False

    _grant_role_permission("visitor", "audit:read")
    response = client.get(
        f"/api/v1/qa/{ask_payload['request_id']}/graph",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["graph_paths"] == []
    assert any("omitted" in item.lower() or "no authorized" in item.lower() for item in payload["security_notes"])


def test_qa_graph_endpoint_respects_request_ownership_and_permission(client):
    cn_token = _login(client, "sales_staff@example.local")
    en_token = _login(client, "tech_staff@example.local")

    ask_payload = _ask(client, cn_token, f"请描述公开制度图谱 {uuid4().hex}", mode="graphrag")
    request_id = ask_payload["request_id"]

    forbidden = client.get(
        f"/api/v1/qa/{request_id}/graph",
        headers={"Authorization": f"Bearer {en_token}"},
    )
    assert forbidden.status_code == 403, forbidden.text

    owner = client.get(
        f"/api/v1/qa/{request_id}/graph",
        headers={"Authorization": f"Bearer {cn_token}"},
    )
    assert owner.status_code == 200, owner.text
    owner_payload = owner.json()
    assert owner_payload["request_id"] == request_id
    assert set(owner_payload["allowed_kb_codes"]) == {"public-policy", "sales-internal"}


def test_neo4j_unavailable_fallback_does_not_break_graphrag_qa(client):
    previous = neo4j_service._disabled
    neo4j_service._disabled = True
    try:
        token = _login(client, "sales_staff@example.local")
        ask_payload = _ask(client, token, f"请给我公开政策图谱说明 {uuid4().hex}", mode="graphrag")
        assert ask_payload["denied"] is False

        trace_response = client.get(
            f"/api/v1/qa/{ask_payload['request_id']}/trace",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert trace_response.status_code == 200, trace_response.text
        steps = {item["tool_name"]: item for item in trace_response.json()["function_trace"]}
        assert steps["get_graph_paths"]["status"] == "success"
        assert "fallback=true" in steps["get_graph_paths"]["output_summary"]
    finally:
        neo4j_service._disabled = previous
