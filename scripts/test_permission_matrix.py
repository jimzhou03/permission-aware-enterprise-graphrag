from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PASSWORD = "Passw0rd!123"


@dataclass(frozen=True)
class AccountCase:
    role: str
    email: str
    expected_kb_codes: set[str]
    allowed_question: str
    overreach_kb_code: str | None = None
    overreach_question: str | None = None


ACCOUNTS: list[AccountCase] = [
    AccountCase(
        role="visitor",
        email="visitor@example.local",
        expected_kb_codes={"public-policy"},
        allowed_question="请介绍星海智造机器人有限公司公开产品线。",
        overreach_kb_code="hr-internal",
        overreach_question="请提供人事部考勤制度。",
    ),
    AccountCase(
        role="tech_staff",
        email="tech_staff@example.local",
        expected_kb_codes={"tech-internal", "company-internal", "public-policy"},
        allowed_question="技术部机器人故障诊断流程是什么？",
        overreach_kb_code="sales-internal",
        overreach_question="Summarize sales pricing policy.",
    ),
    AccountCase(
        role="sales_staff",
        email="sales_staff@example.local",
        expected_kb_codes={"sales-internal", "company-internal", "public-policy"},
        allowed_question="销售部本季度客户策略是什么？",
        overreach_kb_code="tech-internal",
        overreach_question="请总结技术部 SDK 部署排障流程。",
    ),
    AccountCase(
        role="marketing_staff",
        email="marketing_staff@example.local",
        expected_kb_codes={"marketing-internal", "company-internal", "public-policy"},
        allowed_question="市场部品牌定位是什么？",
        overreach_kb_code="support-internal",
        overreach_question="请总结客服部售后流程。",
    ),
    AccountCase(
        role="support_staff",
        email="support_staff@example.local",
        expected_kb_codes={"support-internal", "company-internal", "public-policy"},
        allowed_question="客服部售后处理流程是什么？",
        overreach_kb_code="product-internal",
        overreach_question="请总结产品部功能路线图。",
    ),
    AccountCase(
        role="hr_staff",
        email="hr_staff@example.local",
        expected_kb_codes={"hr-internal", "company-internal", "public-policy"},
        allowed_question="HR 招人流程是什么？",
        overreach_kb_code="admin-internal",
        overreach_question="请总结行政部采购流程。",
    ),
    AccountCase(
        role="admin_staff",
        email="admin_staff@example.local",
        expected_kb_codes={"admin-internal", "company-internal", "public-policy"},
        allowed_question="行政部采购流程是什么？",
        overreach_kb_code="hr-internal",
        overreach_question="请总结人事部考勤制度。",
    ),
    AccountCase(
        role="product_staff",
        email="product_staff@example.local",
        expected_kb_codes={"product-internal", "company-internal", "public-policy"},
        allowed_question="产品生产流程是什么？",
        overreach_kb_code="marketing-internal",
        overreach_question="请总结市场部宣传内容规范。",
    ),
    AccountCase(
        role="bilingual_admin",
        email="bilingual_admin@example.local",
        expected_kb_codes={
            "public-policy",
            "company-internal",
            "tech-internal",
            "sales-internal",
            "marketing-internal",
            "support-internal",
            "hr-internal",
            "admin-internal",
            "product-internal",
        },
        allowed_question="Summarize authorized support and product policies.",
    ),
]


class PermissionMatrixFailure(Exception):
    pass


def _request_json(
    method: str,
    url: str,
    payload: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, method=method, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            data = json.loads(text) if text else {}
            return response.status, data
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            data = {"raw": text}
        return exc.code, data


def _assert_equal(name: str, actual, expected, context: dict) -> None:
    if actual != expected:
        raise PermissionMatrixFailure(
            f"[FAIL] {name}: expected={expected!r}, actual={actual!r}, context={json.dumps(context, ensure_ascii=False)}"
        )


def _assert_true(name: str, condition: bool, context: dict) -> None:
    if not condition:
        raise PermissionMatrixFailure(f"[FAIL] {name}: context={json.dumps(context, ensure_ascii=False)}")


def _assert_citations_in_scope(name: str, ask_data: dict, allowed_codes: set[str], context: dict) -> None:
    citations = ask_data.get("citations", [])
    if not isinstance(citations, list):
        raise PermissionMatrixFailure(
            f"[FAIL] {name}: citations is not list, context={json.dumps(context, ensure_ascii=False)}"
        )
    kb_codes = {
        item.get("kb_code")
        for item in citations
        if isinstance(item, dict) and isinstance(item.get("kb_code"), str)
    }
    if not kb_codes.issubset(allowed_codes):
        raise PermissionMatrixFailure(
            f"[FAIL] {name}: unauthorized kb codes={sorted(kb_codes - allowed_codes)!r}, "
            f"context={json.dumps(context, ensure_ascii=False)}"
        )


def _function_status(trace_payload: dict, tool_name: str) -> str:
    for step in trace_payload.get("function_trace", []):
        if isinstance(step, dict) and step.get("tool_name") == tool_name:
            return str(step.get("status"))
    return "missing"


def run(base_url: str) -> int:
    api = f"{base_url.rstrip('/')}/api/v1"
    failures: list[str] = []
    passes = 0
    tokens: dict[str, str] = {}
    denied_request_ids: list[str] = []

    print(f"Running permission matrix test against: {api}")

    for account in ACCOUNTS:
        case_prefix = f"{account.role}<{account.email}>"
        try:
            status, login_data = _request_json(
                "POST",
                f"{api}/auth/login",
                payload={"email": account.email, "password": DEFAULT_PASSWORD},
            )
            _assert_equal(f"{case_prefix} login status", status, 200, {"endpoint": "/auth/login", "response": login_data})
            token = login_data.get("access_token", "")
            _assert_true(f"{case_prefix} token exists", isinstance(token, str) and len(token) > 20, {"response": login_data})

            status, me_data = _request_json("GET", f"{api}/auth/me", token=token)
            _assert_equal(f"{case_prefix} me status", status, 200, {"response": me_data})
            _assert_equal(f"{case_prefix} role match", me_data.get("user", {}).get("role"), account.role, {"response": me_data})

            status, kb_data = _request_json("GET", f"{api}/knowledge-bases", token=token)
            _assert_equal(f"{case_prefix} knowledge-bases status", status, 200, {"response": kb_data})
            kb_codes = {item["code"] for item in kb_data}
            _assert_equal(
                f"{case_prefix} kb scope",
                kb_codes,
                account.expected_kb_codes,
                {"actual": sorted(kb_codes), "expected": sorted(account.expected_kb_codes)},
            )

            status, ask_data = _request_json(
                "POST",
                f"{api}/qa/ask",
                token=token,
                payload={"question": account.allowed_question, "mode": "auto", "knowledge_base_codes": []},
            )
            _assert_equal(f"{case_prefix} allowed ask status", status, 200, {"response": ask_data})
            _assert_true(
                f"{case_prefix} allowed ask not denied",
                ask_data.get("denied") is False,
                {"question": account.allowed_question, "response": ask_data},
            )
            _assert_citations_in_scope(
                f"{case_prefix} allowed ask citation scope",
                ask_data,
                account.expected_kb_codes,
                {"question": account.allowed_question, "response": ask_data},
            )

            if account.overreach_kb_code and account.overreach_question:
                status, denied_ask = _request_json(
                    "POST",
                    f"{api}/qa/ask",
                    token=token,
                    payload={
                        "question": account.overreach_question,
                        "mode": "rag",
                        "knowledge_base_codes": [account.overreach_kb_code],
                    },
                )
                _assert_equal(f"{case_prefix} overreach ask status", status, 200, {"response": denied_ask})
                _assert_true(
                    f"{case_prefix} overreach denied",
                    denied_ask.get("denied") is True,
                    {"response": denied_ask},
                )
                _assert_equal(
                    f"{case_prefix} overreach citations empty",
                    denied_ask.get("citations"),
                    [],
                    {"response": denied_ask},
                )
                denied_request_id = str(denied_ask.get("request_id", ""))
                _assert_true(
                    f"{case_prefix} overreach request_id exists",
                    len(denied_request_id) > 0,
                    {"response": denied_ask},
                )
                denied_request_ids.append(denied_request_id)

                status, trace_data = _request_json("GET", f"{api}/qa/{denied_request_id}/trace", token=token)
                _assert_equal(f"{case_prefix} denied trace status", status, 200, {"response": trace_data})
                _assert_equal(
                    f"{case_prefix} denied trace retrieved_chunks empty",
                    trace_data.get("retrieved_chunks"),
                    [],
                    {"response": trace_data},
                )
                _assert_equal(
                    f"{case_prefix} denied trace hit_chunk_ids empty",
                    trace_data.get("hit_chunk_ids"),
                    [],
                    {"response": trace_data},
                )
                _assert_equal(
                    f"{case_prefix} denied trace search status",
                    _function_status(trace_data, "search_allowed_chunks"),
                    "denied",
                    {"response": trace_data},
                )
                _assert_equal(
                    f"{case_prefix} denied trace generate status",
                    _function_status(trace_data, "generate_answer"),
                    "skipped",
                    {"response": trace_data},
                )

                status, detail_data = _request_json("GET", f"{api}/qa/{denied_request_id}", token=token)
                _assert_equal(f"{case_prefix} denied detail status", status, 200, {"response": detail_data})
                _assert_equal(
                    f"{case_prefix} denied detail hit_chunk_ids empty",
                    detail_data.get("hit_chunk_ids"),
                    [],
                    {"response": detail_data},
                )

                status, graph_data = _request_json("GET", f"{api}/qa/{denied_request_id}/graph", token=token)
                _assert_equal(f"{case_prefix} denied graph status", status, 200, {"response": graph_data})
                _assert_equal(
                    f"{case_prefix} denied graph paths empty",
                    graph_data.get("graph_paths"),
                    [],
                    {"response": graph_data},
                )

            tokens[account.role] = token
            passes += 1
            print(f"[PASS] {case_prefix} login/me/kb/ask")
        except PermissionMatrixFailure as exc:
            failures.append(str(exc))
            print(str(exc))

    try:
        admin_token = tokens.get("bilingual_admin")
        _assert_true("bilingual_admin token exists", bool(admin_token), {"tokens": list(tokens.keys())})
        status, logs = _request_json("GET", f"{api}/admin/audit-logs", token=admin_token)
        _assert_equal("admin audit log status", status, 200, {"response": logs})
        _assert_true("admin audit logs payload is list", isinstance(logs, list), {"response": logs})

        if denied_request_ids:
            denied_rows = [row for row in logs if isinstance(row, dict) and row.get("request_id") in denied_request_ids]
            _assert_true("denied requests present in admin logs", len(denied_rows) > 0, {"denied_request_ids": denied_request_ids})
            for row in denied_rows:
                _assert_equal(
                    "denied audit row hit_chunk_ids empty",
                    row.get("hit_chunk_ids"),
                    [],
                    {"row": row},
                )
        passes += 1
        print("[PASS] admin audit logs safe for denied requests")
    except PermissionMatrixFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    try:
        visitor_token = tokens.get("visitor")
        _assert_true("visitor token exists", bool(visitor_token), {"tokens": list(tokens.keys())})

        status, greeting_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={"question": "你好", "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("visitor greeting ask status", status, 200, {"response": greeting_data})
        _assert_equal("visitor greeting mode", greeting_data.get("mode"), "general", {"response": greeting_data})
        _assert_equal("visitor greeting denied", greeting_data.get("denied"), False, {"response": greeting_data})
        _assert_equal("visitor greeting citations empty", greeting_data.get("citations"), [], {"response": greeting_data})

        status, intro_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={"question": "公司是做什么的？", "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("visitor company intro ask status", status, 200, {"response": intro_data})
        _assert_equal("visitor company intro denied", intro_data.get("denied"), False, {"response": intro_data})
        _assert_true(
            "visitor company intro citations in public-policy",
            {
                item.get("kb_code")
                for item in intro_data.get("citations", [])
                if isinstance(item, dict) and isinstance(item.get("kb_code"), str)
            }.issubset({"public-policy"}),
            {"response": intro_data},
        )

        status, coop_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={"question": "如何商务合作？", "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("visitor cooperation ask status", status, 200, {"response": coop_data})
        _assert_equal("visitor cooperation denied", coop_data.get("denied"), False, {"response": coop_data})

        status, company_internal_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={"question": "公司组织架构是什么？", "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("visitor company internal ask status", status, 200, {"response": company_internal_data})
        _assert_equal("visitor company internal denied", company_internal_data.get("denied"), True, {"response": company_internal_data})
        _assert_equal("visitor company internal citations empty", company_internal_data.get("citations"), [], {"response": company_internal_data})

        status, clarification_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={"question": "内部流程怎么走？", "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("visitor clarification ask status", status, 200, {"response": clarification_data})
        _assert_equal("visitor clarification denied", clarification_data.get("denied"), False, {"response": clarification_data})
        _assert_equal(
            "visitor clarification mode",
            clarification_data.get("mode"),
            "clarification_required",
            {"response": clarification_data},
        )
        _assert_equal("visitor clarification citations empty", clarification_data.get("citations"), [], {"response": clarification_data})
        _assert_equal("visitor clarification sources empty", clarification_data.get("sources"), [], {"response": clarification_data})

        visitor_clarification_request_id = str(clarification_data.get("request_id", ""))
        _assert_true(
            "visitor clarification request_id exists",
            len(visitor_clarification_request_id) > 0,
            {"response": clarification_data},
        )
        status, clarification_trace = _request_json(
            "GET",
            f"{api}/qa/{visitor_clarification_request_id}/trace",
            token=visitor_token,
        )
        _assert_equal("visitor clarification trace status", status, 200, {"response": clarification_trace})
        _assert_equal(
            "visitor clarification trace search status",
            _function_status(clarification_trace, "search_allowed_chunks"),
            "skipped",
            {"response": clarification_trace},
        )
        _assert_equal(
            "visitor clarification trace generate status",
            _function_status(clarification_trace, "generate_answer"),
            "skipped",
            {"response": clarification_trace},
        )

        for role in [
            "tech_staff",
            "sales_staff",
            "marketing_staff",
            "support_staff",
            "hr_staff",
            "admin_staff",
            "product_staff",
        ]:
            token = tokens.get(role)
            _assert_true(f"{role} token exists", bool(token), {"tokens": list(tokens.keys())})
            status, staff_company_data = _request_json(
                "POST",
                f"{api}/qa/ask",
                token=token,
                payload={"question": "怎么申请权限？", "mode": "auto", "knowledge_base_codes": []},
            )
            _assert_equal(f"{role} company ask status", status, 200, {"response": staff_company_data})
            _assert_equal(f"{role} company ask denied", staff_company_data.get("denied"), False, {"response": staff_company_data})
            _assert_true(
                f"{role} company ask citations in company-internal",
                {
                    item.get("kb_code")
                    for item in staff_company_data.get("citations", [])
                    if isinstance(item, dict) and isinstance(item.get("kb_code"), str)
                }.issubset({"company-internal"}),
                {"response": staff_company_data},
            )
            _assert_true(
                f"{role} company ask sources sanitized",
                all(
                    isinstance(item, dict)
                    and set(item.keys()) == {"kb_code", "kb_name", "document_title"}
                    for item in staff_company_data.get("sources", [])
                ),
                {"response": staff_company_data},
            )

        passes += 1
        print("[PASS] visitor general/public-quality questions")
    except PermissionMatrixFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    total = len(ACCOUNTS) + 2
    print("")
    print(f"Result: {passes}/{total} PASS")
    if failures:
        print("Failures:")
        for idx, failure in enumerate(failures, start=1):
            print(f"{idx}. {failure}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Permission matrix smoke test for API role scopes.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="API host base URL, default: http://127.0.0.1:8000",
    )
    args = parser.parse_args()
    return run(args.base_url)


if __name__ == "__main__":
    sys.exit(main())
