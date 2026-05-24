def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_and_me(client):
    token = _login(client, "hr@example.local")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "hr@example.local"
    assert payload["user"]["role"] == "hr"
    assert payload["permission_scope"]["department"] == "hr"


def test_invalid_login_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "hr@example.local", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_visitor_scope_only_public(client):
    token = _login(client, "visitor@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == ["public-general"]


def test_hr_scope_excludes_finance_and_tech(client):
    token = _login(client, "hr@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert "public-general" in codes
    assert "hr-policy" in codes
    assert "finance-policy" not in codes
    assert "tech-policy" not in codes


def test_admin_scope_has_all_seed_kbs(client):
    token = _login(client, "admin@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == ["finance-policy", "hr-policy", "public-general", "tech-policy"]

