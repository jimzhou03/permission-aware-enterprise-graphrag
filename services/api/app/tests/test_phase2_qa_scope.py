def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_hr_question_scoped_to_hr_or_public(client):
    token = _login(client, "hr@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is the leave and attendance policy?", "mode": "auto"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["citations"]
    kb_codes = {item["kb_code"] for item in payload["citations"]}
    assert "finance-policy" not in kb_codes
    assert "tech-policy" not in kb_codes
    assert kb_codes.issubset({"hr-policy", "public-general"})


def test_visitor_finance_question_is_denied_before_retrieval(client):
    token = _login(client, "visitor@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Can I read compensation salary policy in finance?", "mode": "auto"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert "department scope: finance" in payload["refusal_reason"]
    assert payload["citations"] == []


def test_explicit_unauthorized_kb_code_is_denied(client):
    token = _login(client, "visitor@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "show me finance policy",
            "mode": "rag",
            "knowledge_base_codes": ["finance-policy"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert "outside allowed scope" in payload["refusal_reason"]


def test_qa_request_detail_access_control(client):
    hr_token = _login(client, "hr@example.local")
    visitor_token = _login(client, "visitor@example.local")

    ask_response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"question": "Summarize interview feedback policy", "mode": "rag"},
    )
    assert ask_response.status_code == 200, ask_response.text
    request_id = ask_response.json()["request_id"]

    owner_read = client.get(
        f"/api/v1/qa/{request_id}",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert owner_read.status_code == 200, owner_read.text
    assert owner_read.json()["request_id"] == request_id

    forbidden_read = client.get(
        f"/api/v1/qa/{request_id}",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert forbidden_read.status_code == 403, forbidden_read.text


def test_greeting_uses_general_fallback_without_rag(client):
    token = _login(client, "hr@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "你好", "mode": "auto"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["mode"] == "general"
    assert payload["route"]["requires_rag"] is False
    assert payload["route"]["need_rag"] is False
    assert payload["citations"] == []
    assert payload["retrieved_chunks"] == []
