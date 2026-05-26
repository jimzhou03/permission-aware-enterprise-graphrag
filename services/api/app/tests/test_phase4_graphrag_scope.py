from uuid import uuid4


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_graphrag_sales_staff_returns_graph_paths_in_authorized_scope(client):
    token = _login(client, "sales_staff@example.local")
    question = f"请给出销售内部手册图谱证据 {uuid4().hex}"
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
    assert {item["kb_code"] for item in payload["citations"]}.issubset({"sales-internal"})

    allowed_prefixes = {"KB:sales-internal"}
    for graph_path in payload["graph_paths"]:
        assert graph_path["path"], graph_path
        assert graph_path["path"][0] in allowed_prefixes
        assert "public-policy" not in " ".join(graph_path["path"])
        assert "tech-internal" not in " ".join(graph_path["path"])
        assert "marketing-internal" not in " ".join(graph_path["path"])


def test_graphrag_visitor_sales_internal_request_denied(client):
    token = _login(client, "visitor@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "请给我销售部内部手册图谱详情", "mode": "graphrag"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert payload["citations"] == []
    assert payload["graph_paths"] == []
