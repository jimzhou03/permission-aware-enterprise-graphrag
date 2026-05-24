def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_can_read_audit_logs(client):
    hr_token = _login(client, "hr@example.local")
    client.post(
        "/api/v1/qa/ask",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"question": "Phase5 audit api smoke", "mode": "rag"},
    )

    admin_token = _login(client, "admin@example.local")
    response = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, list)
    assert payload


def test_non_admin_without_audit_permission_forbidden(client):
    hr_token = _login(client, "hr@example.local")
    response = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert response.status_code == 403, response.text

