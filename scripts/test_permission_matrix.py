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


ACCOUNTS: list[AccountCase] = [
    AccountCase(
        role="bilingual_admin",
        email="bilingual_admin@example.local",
        expected_kb_codes={"cn-public", "cn-internal", "en-public", "en-internal", "public-policy"},
        allowed_question="Summarize visitor guidance and internal onboarding checklist.",
    ),
    AccountCase(
        role="cn_staff",
        email="cn_staff@example.local",
        expected_kb_codes={"cn-public", "cn-internal"},
        allowed_question="请总结中文内部手册中的接入流程。",
    ),
    AccountCase(
        role="en_staff",
        email="en_staff@example.local",
        expected_kb_codes={"en-public", "en-internal"},
        allowed_question="Summarize the English internal onboarding flow.",
    ),
    AccountCase(
        role="visitor",
        email="visitor@example.local",
        expected_kb_codes={"public-policy"},
        allowed_question="Summarize visitor badge and public support guidance.",
    ),
]


class TestFailure(Exception):
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
        raise TestFailure(
            f"[FAIL] {name}: expected={expected!r}, actual={actual!r}, context={json.dumps(context, ensure_ascii=False)}"
        )


def _assert_true(name: str, condition: bool, context: dict) -> None:
    if not condition:
        raise TestFailure(f"[FAIL] {name}: context={json.dumps(context, ensure_ascii=False)}")


def _assert_citations_in_scope(name: str, ask_data: dict, allowed_codes: set[str], context: dict) -> None:
    citations = ask_data.get("citations", [])
    if not isinstance(citations, list):
        raise TestFailure(f"[FAIL] {name}: citations is not list, context={json.dumps(context, ensure_ascii=False)}")
    kb_codes = {
        item.get("kb_code")
        for item in citations
        if isinstance(item, dict) and isinstance(item.get("kb_code"), str)
    }
    if not kb_codes.issubset(allowed_codes):
        raise TestFailure(
            f"[FAIL] {name}: unauthorized kb codes={sorted(kb_codes - allowed_codes)!r}, "
            f"context={json.dumps(context, ensure_ascii=False)}"
        )


def run(base_url: str) -> int:
    api = f"{base_url.rstrip('/')}/api/v1"
    failures: list[str] = []
    passes = 0
    tokens: dict[str, str] = {}

    print(f"Running permission matrix test against: {api}")

    for account in ACCOUNTS:
        case_prefix = f"{account.role}<{account.email}>"
        try:
            status, login_data = _request_json(
                "POST",
                f"{api}/auth/login",
                payload={"email": account.email, "password": DEFAULT_PASSWORD},
            )
            _assert_equal(
                f"{case_prefix} login status",
                status,
                200,
                {"endpoint": "/auth/login", "response": login_data},
            )
            token = login_data.get("access_token", "")
            _assert_true(
                f"{case_prefix} token exists",
                isinstance(token, str) and len(token) > 20,
                {"endpoint": "/auth/login", "response": login_data},
            )

            status, me_data = _request_json(
                "GET",
                f"{api}/auth/me",
                token=token,
            )
            _assert_equal(
                f"{case_prefix} me status",
                status,
                200,
                {"endpoint": "/auth/me", "response": me_data},
            )
            me_role = me_data.get("user", {}).get("role")
            _assert_equal(
                f"{case_prefix} role match",
                me_role,
                account.role,
                {"endpoint": "/auth/me", "response": me_data},
            )

            status, kb_data = _request_json(
                "GET",
                f"{api}/knowledge-bases",
                token=token,
            )
            _assert_equal(
                f"{case_prefix} knowledge-bases status",
                status,
                200,
                {"endpoint": "/knowledge-bases", "response": kb_data},
            )
            kb_codes = {item["code"] for item in kb_data}
            _assert_equal(
                f"{case_prefix} kb scope",
                kb_codes,
                account.expected_kb_codes,
                {"endpoint": "/knowledge-bases", "kb_codes": sorted(kb_codes), "response": kb_data},
            )

            status, ask_data = _request_json(
                "POST",
                f"{api}/qa/ask",
                token=token,
                payload={"question": account.allowed_question, "mode": "auto", "knowledge_base_codes": []},
            )
            _assert_equal(
                f"{case_prefix} ask status",
                status,
                200,
                {"endpoint": "/qa/ask", "response": ask_data},
            )
            _assert_true(
                f"{case_prefix} allowed question should not be denied",
                ask_data.get("denied") is False,
                {
                    "endpoint": "/qa/ask",
                    "question": account.allowed_question,
                    "response": ask_data,
                },
            )
            _assert_citations_in_scope(
                f"{case_prefix} allowed question citation scope",
                ask_data,
                account.expected_kb_codes,
                {
                    "endpoint": "/qa/ask",
                    "question": account.allowed_question,
                    "response": ask_data,
                },
            )

            tokens[account.role] = token
            passes += 1
            print(f"[PASS] {case_prefix} login/me/kb/ask")
        except TestFailure as exc:
            failures.append(str(exc))
            print(str(exc))

    # Required overreach check: visitor asks finance salary policy must be denied.
    try:
        visitor_token = tokens.get("visitor")
        _assert_true("visitor token exists for overreach", bool(visitor_token), {"tokens": list(tokens.keys())})

        status, ask_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=visitor_token,
            payload={
                "question": "finance compensation salary policy",
                "mode": "auto",
                "knowledge_base_codes": [],
            },
        )
        _assert_equal(
            "visitor finance overreach ask status",
            status,
            200,
            {"endpoint": "/qa/ask", "response": ask_data},
        )
        _assert_true(
            "visitor finance overreach denied",
            ask_data.get("denied") is True,
            {"endpoint": "/qa/ask", "question": "finance compensation salary policy", "response": ask_data},
        )
        _assert_true(
            "visitor finance overreach no citations",
            ask_data.get("citations", []) == [],
            {"endpoint": "/qa/ask", "question": "finance compensation salary policy", "response": ask_data},
        )
        passes += 1
        print("[PASS] visitor finance overreach denied")
    except TestFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    # cn_staff cross-language isolation: asking English internal should be denied
    # OR return only authorized CN chunks.
    try:
        cn_token = tokens.get("cn_staff")
        _assert_true("cn_staff token exists", bool(cn_token), {"tokens": list(tokens.keys())})
        question = "Explain the English internal handbook onboarding checklist."
        status, ask_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=cn_token,
            payload={"question": question, "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("cn_staff cross-language ask status", status, 200, {"endpoint": "/qa/ask", "response": ask_data})
        if ask_data.get("denied") is not True:
            _assert_citations_in_scope(
                "cn_staff cross-language scoped citations",
                ask_data,
                {"cn-public", "cn-internal"},
                {"endpoint": "/qa/ask", "question": question, "response": ask_data},
            )
        passes += 1
        print("[PASS] cn_staff English-internal isolation")
    except TestFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    # en_staff cross-language isolation: asking Chinese internal should be denied
    # OR return only authorized EN chunks.
    try:
        en_token = tokens.get("en_staff")
        _assert_true("en_staff token exists", bool(en_token), {"tokens": list(tokens.keys())})
        question = "请解释中文内部手册中的接入流程和协作约定。"
        status, ask_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=en_token,
            payload={"question": question, "mode": "auto", "knowledge_base_codes": []},
        )
        _assert_equal("en_staff cross-language ask status", status, 200, {"endpoint": "/qa/ask", "response": ask_data})
        if ask_data.get("denied") is not True:
            _assert_citations_in_scope(
                "en_staff cross-language scoped citations",
                ask_data,
                {"en-public", "en-internal"},
                {"endpoint": "/qa/ask", "question": question, "response": ask_data},
            )
        passes += 1
        print("[PASS] en_staff Chinese-internal isolation")
    except TestFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    # bilingual_admin bilingual retrieval with explicit kb scope
    try:
        admin_token = tokens.get("bilingual_admin")
        _assert_true("bilingual_admin token exists", bool(admin_token), {"tokens": list(tokens.keys())})

        cn_status, cn_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=admin_token,
            payload={
                "question": "请总结中文内部手册中的接入流程。",
                "mode": "rag",
                "knowledge_base_codes": ["cn-internal"],
            },
        )
        _assert_equal("bilingual_admin cn ask status", cn_status, 200, {"endpoint": "/qa/ask", "response": cn_data})
        _assert_true(
            "bilingual_admin cn ask not denied",
            cn_data.get("denied") is False,
            {"endpoint": "/qa/ask", "response": cn_data},
        )
        _assert_citations_in_scope(
            "bilingual_admin cn citations",
            cn_data,
            {"cn-internal"},
            {"endpoint": "/qa/ask", "response": cn_data},
        )

        en_status, en_data = _request_json(
            "POST",
            f"{api}/qa/ask",
            token=admin_token,
            payload={
                "question": "Summarize the English internal onboarding checklist.",
                "mode": "rag",
                "knowledge_base_codes": ["en-internal"],
            },
        )
        _assert_equal("bilingual_admin en ask status", en_status, 200, {"endpoint": "/qa/ask", "response": en_data})
        _assert_true(
            "bilingual_admin en ask not denied",
            en_data.get("denied") is False,
            {"endpoint": "/qa/ask", "response": en_data},
        )
        _assert_citations_in_scope(
            "bilingual_admin en citations",
            en_data,
            {"en-internal"},
            {"endpoint": "/qa/ask", "response": en_data},
        )

        passes += 1
        print("[PASS] bilingual_admin bilingual retrieval")
    except TestFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    total = len(ACCOUNTS) + 4
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
