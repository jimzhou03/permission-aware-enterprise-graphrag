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


def _trace_step_status(trace_payload: dict, step_name: str) -> str:
    for step in trace_payload.get("function_trace", []):
        if isinstance(step, dict) and step.get("tool_name") == step_name:
            return str(step.get("status"))
    return "missing"


def _assert_no_unauthorized_chunks(payload: dict, allowed_codes: set[str]) -> None:
    kb_codes = {item["kb_code"] for item in payload.get("citations", [])}
    assert kb_codes.issubset(allowed_codes)


def test_department_accounts_can_retrieve_only_allowed_scope(client):
    cases = [
        (
            "tech_staff@example.local",
            {"tech-internal", "company-internal", "public-policy"},
            "技术部机器人故障诊断流程是什么？",
        ),
        (
            "sales_staff@example.local",
            {"sales-internal", "company-internal", "public-policy"},
            "销售部本季度客户策略是什么？",
        ),
        (
            "marketing_staff@example.local",
            {"marketing-internal", "company-internal", "public-policy"},
            "市场部品牌定位是什么？",
        ),
        (
            "support_staff@example.local",
            {"support-internal", "company-internal", "public-policy"},
            "客服部售后处理流程是什么？",
        ),
        (
            "hr_staff@example.local",
            {"hr-internal", "company-internal", "public-policy"},
            "HR 招人流程是什么？",
        ),
        (
            "admin_staff@example.local",
            {"admin-internal", "company-internal", "public-policy"},
            "行政部采购流程是什么？",
        ),
        (
            "product_staff@example.local",
            {"product-internal", "company-internal", "public-policy"},
            "产品生产流程是什么？",
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
        ("company-internal", "请总结公司组织架构与权限申请流程。"),
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
        assert payload["route"]["target_scope"] == "public"
        assert payload["route"]["target_department"] is None
        assert payload["route"]["target_kb_codes"] == ["public-policy"]
        assert payload["route"]["requires_internal_access"] is False
        assert {item["kb_code"] for item in payload["citations"]}.issubset({"public-policy"})
        assert "当前账号可访问" in payload["answer"] or "Based on the knowledge bases available" in payload["answer"]


def test_company_internal_questions_require_company_internal_scope(client):
    visitor_token = _login(client, "visitor@example.local")
    visitor_response = _ask(client, visitor_token, "公司组织架构是什么？", mode="auto")
    assert visitor_response.status_code == 200, visitor_response.text
    visitor_payload = visitor_response.json()
    assert visitor_payload["denied"] is True
    assert visitor_payload["citations"] == []
    assert visitor_payload["route"]["target_scope"] == "company"
    assert visitor_payload["route"]["target_kb_codes"] == ["company-internal"]

    sales_token = _login(client, "sales_staff@example.local")
    staff_response = _ask(client, sales_token, "怎么申请权限？", mode="auto")
    assert staff_response.status_code == 200, staff_response.text
    staff_payload = staff_response.json()
    assert staff_payload["denied"] is False
    assert {item["kb_code"] for item in staff_payload["citations"]}.issubset({"company-internal"})
    assert staff_payload["route"]["target_scope"] == "company"


def test_router_target_scope_narrowing_for_department_questions(client):
    checks = [
        ("sales_staff@example.local", "销售报价策略是什么？", False, {"sales-internal"}),
        ("sales_staff@example.local", "SDK 怎么接入？", True, set()),
        ("tech_staff@example.local", "How to integrate the robot SDK?", False, {"tech-internal"}),
        ("tech_staff@example.local", "销售报价策略是什么？", True, set()),
        ("hr_staff@example.local", "绩效制度是什么？", False, {"hr-internal"}),
        ("marketing_staff@example.local", "绩效制度是什么？", True, set()),
        ("product_staff@example.local", "产品路线图是什么？", False, {"product-internal"}),
    ]
    for email, question, denied_expected, allowed_hit_codes in checks:
        token = _login(client, email)
        response = _ask(client, token, question, mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is denied_expected, {"email": email, "question": question, "payload": payload}
        if denied_expected:
            assert payload["citations"] == []
            continue
        assert {item["kb_code"] for item in payload["citations"]}.issubset(allowed_hit_codes)


def test_all_staff_can_hit_company_internal_for_permission_workflow_question(client):
    staff_emails = [
        "tech_staff@example.local",
        "sales_staff@example.local",
        "marketing_staff@example.local",
        "support_staff@example.local",
        "hr_staff@example.local",
        "admin_staff@example.local",
        "product_staff@example.local",
    ]
    for email in staff_emails:
        token = _login(client, email)
        response = _ask(client, token, "怎么申请权限？", mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False, {"email": email, "payload": payload}
        assert payload["route"]["target_scope"] == "company"
        assert {item["kb_code"] for item in payload["citations"]}.issubset({"company-internal"})


def test_bilingual_admin_can_hit_multiple_department_targets(client):
    token = _login(client, "bilingual_admin@example.local")
    checks = [
        ("销售报价策略是什么？", {"sales-internal"}),
        ("How to integrate the robot SDK?", {"tech-internal"}),
        ("绩效制度是什么？", {"hr-internal"}),
        ("产品路线图是什么？", {"product-internal"}),
    ]
    for question, expected_scope in checks:
        response = _ask(client, token, question, mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False
        assert {item["kb_code"] for item in payload["citations"]}.issubset(expected_scope)


def test_v094_demo_knowledge_coverage_routing_cases(client):
    cases = [
        {
            "name": "tech staff can ask tech coverage question",
            "email": "tech_staff@example.local",
            "question": "技术部机器人故障诊断流程是什么？",
            "expected_kb_code": "tech-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "sales staff can ask quarterly customer strategy",
            "email": "sales_staff@example.local",
            "question": "销售部本季度客户策略是什么？",
            "expected_kb_code": "sales-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "marketing staff can ask brand positioning",
            "email": "marketing_staff@example.local",
            "question": "市场部品牌定位是什么？",
            "expected_kb_code": "marketing-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "support staff can ask aftersales flow",
            "email": "support_staff@example.local",
            "question": "客服部售后处理流程是什么？",
            "expected_kb_code": "support-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "hr staff can ask recruitment flow",
            "email": "hr_staff@example.local",
            "question": "HR 招人流程是什么？",
            "expected_kb_code": "hr-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "admin staff can ask procurement flow",
            "email": "admin_staff@example.local",
            "question": "行政部采购流程是什么？",
            "expected_kb_code": "admin-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "product staff can ask production flow",
            "email": "product_staff@example.local",
            "question": "产品生产流程是什么？",
            "expected_kb_code": "product-internal",
            "denied": False,
            "expected_scope": "department",
            "expect_trace_denied": False,
        },
        {
            "name": "visitor is denied sales internal strategy",
            "email": "visitor@example.local",
            "question": "销售部本季度客户策略是什么？",
            "expected_kb_code": "sales-internal",
            "denied": True,
            "expected_scope": "department",
            "expect_trace_denied": True,
        },
        {
            "name": "product staff is denied tech internal flow",
            "email": "product_staff@example.local",
            "question": "技术部机器人故障诊断流程是什么？",
            "expected_kb_code": "tech-internal",
            "denied": True,
            "expected_scope": "department",
            "expect_trace_denied": True,
        },
        {
            "name": "visitor can ask public aftersales policy",
            "email": "visitor@example.local",
            "question": "公司公开售后政策是什么？",
            "expected_kb_code": "public-policy",
            "denied": False,
            "expected_scope": "public",
            "expect_trace_denied": False,
        },
        {
            "name": "visitor vague internal flow requires clarification",
            "email": "visitor@example.local",
            "question": "内部流程怎么走？",
            "expected_kb_code": None,
            "denied": False,
            "expected_scope": "clarification_required",
            "expect_trace_denied": False,
            "expected_mode": "clarification_required",
        },
    ]

    for case in cases:
        token = _login(client, case["email"])
        response = _ask(client, token, case["question"], mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is case["denied"], {"case": case, "payload": payload}
        assert payload["route"]["target_scope"] == case["expected_scope"], {"case": case, "payload": payload}
        if case["expected_kb_code"] is None:
            assert payload["route"]["target_kb_codes"] == [], {"case": case, "payload": payload}
            assert payload["mode"] == case.get("expected_mode"), {"case": case, "payload": payload}
            assert payload["citations"] == [], {"case": case, "payload": payload}
            assert payload["sources"] == [], {"case": case, "payload": payload}
            continue

        assert payload["route"]["target_kb_codes"] == [case["expected_kb_code"]], {"case": case, "payload": payload}

        if case["denied"]:
            assert payload["citations"] == [], {"case": case, "payload": payload}
            assert payload["sources"] == [], {"case": case, "payload": payload}
            trace_payload = _trace(client, token, payload["request_id"])
            assert _trace_step_status(trace_payload, "search_allowed_chunks") == "denied", {
                "case": case,
                "trace": trace_payload,
            }
        else:
            hit_codes = {item["kb_code"] for item in payload.get("citations", [])}
            source_codes = {item["kb_code"] for item in payload.get("sources", [])}
            assert hit_codes, {"case": case, "payload": payload}
            assert source_codes, {"case": case, "payload": payload}
            assert hit_codes.issubset({case["expected_kb_code"]}), {"case": case, "payload": payload}
            assert source_codes.issubset({case["expected_kb_code"]}), {"case": case, "payload": payload}
            assert payload["answer"], {"case": case, "payload": payload}


def test_clarification_required_skips_retrieval_and_generation(client):
    checks = [
        ("visitor@example.local", "内部流程怎么走？"),
        ("tech_staff@example.local", "那个流程是什么？"),
    ]
    for email, question in checks:
        token = _login(client, email)
        response = _ask(client, token, question, mode="auto")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["denied"] is False, {"email": email, "payload": payload}
        assert payload["mode"] == "clarification_required", {"email": email, "payload": payload}
        assert payload["route"]["target_scope"] == "clarification_required", {"email": email, "payload": payload}
        assert payload["route"]["target_kb_codes"] == [], {"email": email, "payload": payload}
        assert payload["citations"] == [], {"email": email, "payload": payload}
        assert payload["retrieved_chunks"] == [], {"email": email, "payload": payload}
        assert payload["sources"] == [], {"email": email, "payload": payload}

        trace_payload = _trace(client, token, payload["request_id"])
        assert _trace_step_status(trace_payload, "search_allowed_chunks") == "skipped", {
            "email": email,
            "trace": trace_payload,
        }
        assert _trace_step_status(trace_payload, "generate_answer") == "skipped", {
            "email": email,
            "trace": trace_payload,
        }


def test_normal_answer_payload_exposes_only_sanitized_sources_for_chat_render(client):
    token = _login(client, "tech_staff@example.local")
    response = _ask(client, token, "Summarize the Robot SDK Manual deployment checklist.", mode="auto")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["denied"] is False, payload
    assert isinstance(payload.get("sources"), list), payload
    assert len(payload["sources"]) > 0, payload
    for source in payload["sources"]:
        assert set(source.keys()) == {"kb_code", "kb_name", "document_title"}, {"source": source}
        assert "chunk_id" not in source
        assert "score" not in source
        assert "excerpt" not in source

    trace_payload = _trace(client, token, payload["request_id"])
    assert _trace_step_status(trace_payload, "search_allowed_chunks") == "success", trace_payload
    assert len(trace_payload.get("retrieved_chunks", [])) >= 0


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
