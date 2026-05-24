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
        role="admin",
        email="admin@example.local",
        expected_kb_codes={"public-general", "hr-policy", "finance-policy", "tech-policy"},
        allowed_question="Summarize all company policy categories.",
    ),
    AccountCase(
        role="hr",
        email="hr@example.local",
        expected_kb_codes={"public-general", "hr-policy"},
        allowed_question="Summarize leave and attendance policy.",
    ),
    AccountCase(
        role="finance",
        email="finance@example.local",
        expected_kb_codes={"public-general", "finance-policy"},
        allowed_question="Summarize reimbursement policy details.",
    ),
    AccountCase(
        role="tech",
        email="tech@example.local",
        expected_kb_codes={"public-general", "tech-policy"},
        allowed_question="Summarize release runbook checklist.",
    ),
    AccountCase(
        role="visitor",
        email="visitor@example.local",
        expected_kb_codes={"public-general"},
        allowed_question="Summarize public employee handbook.",
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


def run(base_url: str) -> int:
    api = f"{base_url.rstrip('/')}/api/v1"
    failures: list[str] = []
    passes = 0

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

            passes += 1
            print(f"[PASS] {case_prefix} login/me/kb/ask")
        except TestFailure as exc:
            failures.append(str(exc))
            print(str(exc))

    # Required overreach checks
    try:
        status, login_data = _request_json(
            "POST",
            f"{api}/auth/login",
            payload={"email": "visitor@example.local", "password": DEFAULT_PASSWORD},
        )
        _assert_equal("visitor overreach login status", status, 200, {"endpoint": "/auth/login", "response": login_data})
        visitor_token = login_data["access_token"]

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
        passes += 1
        print("[PASS] visitor finance overreach denied")
    except TestFailure as exc:
        failures.append(str(exc))
        print(str(exc))

    total = len(ACCOUNTS) + 1
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
