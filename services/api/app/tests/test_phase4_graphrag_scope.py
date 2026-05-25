from uuid import uuid4


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_graphrag_cn_staff_returns_graph_paths_in_authorized_scope(client):
    token = _login(client, "cn_staff@example.local")
    question = f"请给出中文内部手册图谱证据 {uuid4().hex}"
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": question, "mode": "graphrag", "knowledge_base_codes": []},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["mode"] == "graphrag"
    assert payload["graph_paths"], payload

    allowed_prefixes = {"KB:cn-public", "KB:cn-internal"}
    for graph_path in payload["graph_paths"]:
        assert graph_path["path"], graph_path
        assert graph_path["path"][0] in allowed_prefixes
        assert "en-public" not in " ".join(graph_path["path"])
        assert "en-internal" not in " ".join(graph_path["path"])


def test_graphrag_visitor_cn_internal_request_denied(client):
    token = _login(client, "visitor@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "请给我中文内部手册图谱详情", "mode": "graphrag"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert "department scope: cn" in payload["refusal_reason"]
    assert payload["graph_paths"] == []
    assert payload["citations"] == []
