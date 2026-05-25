def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_and_me(client):
    token = _login(client, "cn_staff@example.local")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "cn_staff@example.local"
    assert payload["user"]["role"] == "cn_staff"
    assert payload["permission_scope"]["department"] == "cn"


def test_invalid_login_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "cn_staff@example.local", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_visitor_scope_only_public(client):
    token = _login(client, "visitor@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == ["public-policy"]


def test_cn_staff_scope_only_cn_knowledge_bases(client):
    token = _login(client, "cn_staff@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert codes == {"cn-public", "cn-internal"}


def test_en_staff_scope_only_en_knowledge_bases(client):
    token = _login(client, "en_staff@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert codes == {"en-public", "en-internal"}


def test_bilingual_admin_scope_has_all_bilingual_knowledge_bases(client):
    token = _login(client, "bilingual_admin@example.local")
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert codes == {"cn-public", "cn-internal", "en-public", "en-internal", "public-policy"}
