from uuid import uuid4


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_same_user_same_question_hits_cache(client):
    token = _login(client, "hr@example.local")
    question = f"Explain leave policy cache test {uuid4().hex}"
    payload = {"question": question, "mode": "rag", "knowledge_base_codes": []}

    first = client.post("/api/v1/qa/ask", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert first.status_code == 200, first.text
    first_json = first.json()
    assert first_json["cache_hit"] is False
    assert first_json["denied"] is False

    second = client.post("/api/v1/qa/ask", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert second.status_code == 200, second.text
    second_json = second.json()
    assert second_json["cache_hit"] is True
    assert second_json["answer"] == first_json["answer"]

    detail = client.get(
        f"/api/v1/qa/{second_json['request_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["cache_hit"] is True


def test_cache_key_isolation_between_roles(client):
    hr_token = _login(client, "hr@example.local")
    visitor_token = _login(client, "visitor@example.local")
    question = f"workplace handbook cache scope {uuid4().hex}"
    payload = {"question": question, "mode": "auto", "knowledge_base_codes": []}

    hr_first = client.post("/api/v1/qa/ask", headers={"Authorization": f"Bearer {hr_token}"}, json=payload)
    assert hr_first.status_code == 200, hr_first.text
    assert hr_first.json()["cache_hit"] is False

    visitor_first = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {visitor_token}"},
        json=payload,
    )
    assert visitor_first.status_code == 200, visitor_first.text
    assert visitor_first.json()["cache_hit"] is False

    visitor_second = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {visitor_token}"},
        json=payload,
    )
    assert visitor_second.status_code == 200, visitor_second.text
    assert visitor_second.json()["cache_hit"] is True

