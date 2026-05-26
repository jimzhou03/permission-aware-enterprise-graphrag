def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_and_me(client):
    token = _login(client, "tech_staff@example.local")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "tech_staff@example.local"
    assert payload["user"]["role"] == "tech_staff"
    assert payload["permission_scope"]["department"] == "tech"


def test_invalid_login_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "tech_staff@example.local", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_v072_account_scope_matrix(client):
    expected_scope_by_email = {
        "visitor@example.local": {"public-policy"},
        "tech_staff@example.local": {"tech-internal", "company-internal", "public-policy"},
        "sales_staff@example.local": {"sales-internal", "company-internal", "public-policy"},
        "marketing_staff@example.local": {"marketing-internal", "company-internal", "public-policy"},
        "support_staff@example.local": {"support-internal", "company-internal", "public-policy"},
        "hr_staff@example.local": {"hr-internal", "company-internal", "public-policy"},
        "admin_staff@example.local": {"admin-internal", "company-internal", "public-policy"},
        "product_staff@example.local": {"product-internal", "company-internal", "public-policy"},
        "bilingual_admin@example.local": {
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
    }
    for email, expected_codes in expected_scope_by_email.items():
        token = _login(client, email)
        response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        codes = {item["code"] for item in response.json()}
        assert codes == expected_codes, {"email": email, "actual": sorted(codes), "expected": sorted(expected_codes)}


def test_v072_three_layer_kb_structure_exists(client):
    token = _login(client, "bilingual_admin@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    codes = {item["code"] for item in response.json()}
    assert "public-policy" in codes
    assert "company-internal" in codes
    assert {
        "tech-internal",
        "sales-internal",
        "marketing-internal",
        "support-internal",
        "hr-internal",
        "admin-internal",
        "product-internal",
    }.issubset(codes)
