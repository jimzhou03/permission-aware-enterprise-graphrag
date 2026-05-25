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


def _assert_no_unauthorized_chunks(payload: dict, allowed_codes: set[str]) -> None:
    kb_codes = {item["kb_code"] for item in payload.get("citations", [])}
    assert kb_codes.issubset(allowed_codes)


def test_cn_staff_can_retrieve_cn_knowledge_only(client):
    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "请总结中文内部手册里的接入流程和协作约定。", mode="rag")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["citations"]
    _assert_no_unauthorized_chunks(payload, {"cn-public", "cn-internal"})


def test_cn_staff_english_internal_question_denied_or_scoped(client):
    token = _login(client, "cn_staff@example.local")
    response = _ask(client, token, "Explain the English internal handbook onboarding checklist.", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    if payload["denied"] is False:
        _assert_no_unauthorized_chunks(payload, {"cn-public", "cn-internal"})
    else:
        assert "department scope:" in payload["refusal_reason"]


def test_en_staff_can_retrieve_en_knowledge_only(client):
    token = _login(client, "en_staff@example.local")
    response = client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Summarize the English internal onboarding checklist and working rules.", "mode": "rag"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["citations"]
    _assert_no_unauthorized_chunks(payload, {"en-public", "en-internal"})


def test_en_staff_chinese_internal_question_denied_or_scoped(client):
    token = _login(client, "en_staff@example.local")
    response = _ask(client, token, "请解释中文内部手册中的接入流程和协作约定。", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    if payload["denied"] is False:
        _assert_no_unauthorized_chunks(payload, {"en-public", "en-internal"})
    else:
        assert "department scope:" in payload["refusal_reason"]


def test_visitor_can_only_retrieve_public_policy(client):
    token = _login(client, "visitor@example.local")
    response = _ask(client, token, "Summarize visitor badge and public support guidance.", mode="rag")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    _assert_no_unauthorized_chunks(payload, {"public-policy"})


def test_explicit_unauthorized_kb_code_is_denied(client):
    token = _login(client, "visitor@example.local")
    response = _ask(client, token, "show me cn internal policy", mode="rag", knowledge_base_codes=["cn-internal"])
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is True
    assert "outside allowed scope" in payload["refusal_reason"]


def test_bilingual_admin_can_retrieve_both_cn_and_en_department_knowledge(client):
    token = _login(client, "bilingual_admin@example.local")

    cn_response = _ask(
        client,
        token,
        "请总结中文内部手册中的接入流程。",
        mode="rag",
        knowledge_base_codes=["cn-internal"],
    )
    assert cn_response.status_code == 200, cn_response.text
    cn_payload = cn_response.json()
    assert cn_payload["denied"] is False
    assert cn_payload["citations"]
    _assert_no_unauthorized_chunks(cn_payload, {"cn-internal"})

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
    assert en_payload["citations"]
    _assert_no_unauthorized_chunks(en_payload, {"en-internal"})


def test_qa_request_detail_access_control(client):
    owner_token = _login(client, "cn_staff@example.local")
    visitor_token = _login(client, "visitor@example.local")

    ask_response = _ask(client, owner_token, "请总结中文公开指引中的沟通规范。", mode="rag")
    assert ask_response.status_code == 200, ask_response.text
    request_id = ask_response.json()["request_id"]

    owner_read = client.get(
        f"/api/v1/qa/{request_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_read.status_code == 200, owner_read.text
    assert owner_read.json()["request_id"] == request_id

    forbidden_read = client.get(
        f"/api/v1/qa/{request_id}",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert forbidden_read.status_code == 403, forbidden_read.text


def test_greeting_uses_general_fallback_without_rag(client):
    token = _login(client, "cn_staff@example.local")
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
