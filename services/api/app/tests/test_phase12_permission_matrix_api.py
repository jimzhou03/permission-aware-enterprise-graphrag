import json

def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_permission_matrix_allows_only_users_with_admin_user_read_permission(client):
    allowed_emails = ["bilingual_admin@example.local", "admin_staff@example.local"]
    denied_emails = ["visitor@example.local", "tech_staff@example.local", "product_staff@example.local"]

    for email in allowed_emails:
        token = _login(client, email)
        response = client.get(
            "/api/v1/admin/permission-matrix",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, {"email": email, "body": response.text}

    for email in denied_emails:
        token = _login(client, email)
        response = client.get(
            "/api/v1/admin/permission-matrix",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, {"email": email, "body": response.text}


def test_permission_matrix_forbidden_for_non_admin_user(client):
    token = _login(client, "product_staff@example.local")
    response = client.get(
        "/api/v1/admin/permission-matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403, response.text


def test_permission_matrix_payload_is_read_only_and_scope_correct(client):
    token = _login(client, "bilingual_admin@example.local")
    response = client.get(
        "/api/v1/admin/permission-matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert set(payload.keys()) == {"users", "roles", "departments", "knowledge_bases"}
    assert len(payload["users"]) >= 9
    assert len(payload["knowledge_bases"]) >= 9

    user_by_email = {item["email"]: item for item in payload["users"]}
    product_staff = user_by_email["product_staff@example.local"]
    visitor = user_by_email["visitor@example.local"]
    assert set(product_staff["allowed_kb_codes"]) == {
        "public-policy",
        "company-internal",
        "product-internal",
    }
    assert set(visitor["allowed_kb_codes"]) == {"public-policy"}

    for user_item in payload["users"]:
        assert set(user_item.keys()) == {"email", "role", "department", "allowed_kb_codes"}

    serialized = json.dumps(payload).lower()
    for forbidden in ["password", "password_hash", "secret", "jwt", "api key", "api_key", "access_token", "token_type"]:
        assert forbidden not in serialized
