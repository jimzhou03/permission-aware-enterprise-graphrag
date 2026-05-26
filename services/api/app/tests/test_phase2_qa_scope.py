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


def test_department_accounts_can_retrieve_only_allowed_scope(client):
    cases = [
        (
            "tech_staff@example.local",
            {"tech-internal", "public-policy"},
            "Summarize the Robot SDK Manual deployment checklist.",
        ),
        (
            "sales_staff@example.local",
            {"sales-internal", "public-policy"},
            "请总结销售部机器人产品报价策略。",
        ),
        (
            "marketing_staff@example.local",
            {"marketing-internal", "public-policy"},
            "请说明市场部展会方案与宣传规范。",
        ),
        (
            "support_staff@example.local",
            {"support-internal", "public-policy"},
            "请总结客服部售后流程和保修政策。",
        ),
        (
            "hr_staff@example.local",
            {"hr-internal", "public-policy"},
            "请总结人事部入职流程和考勤制度。",
        ),
        (
            "admin_staff@example.local",
            {"admin-internal", "public-policy"},
            "请总结行政部会议室管理与采购流程。",
        ),
        (
            "product_staff@example.local",
            {"product-internal", "public-policy"},
            "请总结产品部规格与路线图。",
        ),
        (
            "visitor@example.local",
            {"public-policy"},
            "请介绍星海智造机器人有限公司的公开产品线。",
        ),
    ]
    for email, allowed_codes, question in cases:
        token = _login(client, email)
        response = _ask(client, token, question, mode="rag")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False, {"email": email, "payload": payload}
        _assert_no_unauthorized_chunks(payload, allowed_codes)


def test_explicit_unauthorized_kb_scope_is_denied(client):
    checks = [
        ("visitor@example.local", "hr-internal"),
        ("tech_staff@example.local", "sales-internal"),
        ("sales_staff@example.local", "tech-internal"),
        ("marketing_staff@example.local", "support-internal"),
        ("support_staff@example.local", "product-internal"),
        ("hr_staff@example.local", "admin-internal"),
        ("admin_staff@example.local", "hr-internal"),
        ("product_staff@example.local", "marketing-internal"),
    ]
    for email, unauthorized_kb in checks:
        token = _login(client, email)
        response = _ask(
            client,
            token,
            f"show {unauthorized_kb} details",
            mode="rag",
            knowledge_base_codes=[unauthorized_kb],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is True, {"email": email, "kb": unauthorized_kb, "payload": payload}
        assert payload["citations"] == []


def test_bilingual_admin_can_retrieve_all_department_knowledge(client):
    token = _login(client, "bilingual_admin@example.local")
    for kb_code, question in [
        ("tech-internal", "Summarize API integration guide."),
        ("sales-internal", "请总结销售渠道合作政策。"),
        ("marketing-internal", "请总结品牌定位。"),
        ("support-internal", "请总结售后流程。"),
        ("hr-internal", "请总结考勤制度。"),
        ("admin-internal", "请总结采购流程。"),
        ("product-internal", "请总结机器人产品规格。"),
        ("public-policy", "请总结公开产品简介。"),
    ]:
        response = _ask(client, token, question, mode="rag", knowledge_base_codes=[kb_code])
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False
        _assert_no_unauthorized_chunks(payload, {kb_code})


def test_qa_request_detail_access_control(client):
    owner_token = _login(client, "sales_staff@example.local")
    visitor_token = _login(client, "visitor@example.local")

    ask_response = _ask(client, owner_token, "请总结销售部沟通话术。", mode="rag")
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
    token = _login(client, "tech_staff@example.local")
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
    assert payload["route"]["query_language"] == "zh"
    assert payload["route"]["requires_internal_access"] is False
    assert payload["citations"] == []
    assert payload["retrieved_chunks"] == []


def test_identity_and_capability_questions_use_general_fallback(client):
    token = _login(client, "visitor@example.local")
    for question in ["你是谁", "你能做什么", "Who are you", "What can you do"]:
        response = _ask(client, token, question, mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False
        assert payload["mode"] == "general"
        assert payload["citations"] == []
        assert payload["route"]["requires_internal_access"] is False
        assert payload["route"]["intent"] in {"assistant_identity", "assistant_capability"}


def test_company_and_cooperation_questions_use_authorized_public_scope(client):
    token = _login(client, "visitor@example.local")
    for question in ["公司是做什么的？", "有哪些机器人产品？", "如何商务合作？"]:
        response = _ask(client, token, question, mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False
        assert payload["mode"] == "rag"
        assert payload["route"]["target_department"] == "public"
        assert payload["route"]["requires_internal_access"] is False
        assert {item["kb_code"] for item in payload["citations"]}.issubset({"public-policy"})
        assert "当前账号可访问" in payload["answer"] or "Based on the knowledge bases available" in payload["answer"]


def test_unsupported_query_returns_unsupported_mode_without_retrieval(client):
    token = _login(client, "sales_staff@example.local")
    response = _ask(client, token, "?!", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False
    assert payload["mode"] == "unsupported"
    assert payload["citations"] == []
    assert payload["retrieved_chunks"] == []
    assert payload["route"]["intent"] == "unsupported"
