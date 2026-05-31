import json

from sqlalchemy import select

from app.core import database as db_module
from app.core.security import get_password_hash
from app.models import Department, Role, User


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _ensure_admin_user(email: str = "admin@example.local", password: str = "Passw0rd!123") -> None:
    db = db_module.SessionLocal()
    try:
        role = db.scalar(select(Role).where(Role.name == "admin"))
        if role is None:
            role = Role(name="admin", description="System administrator")
            db.add(role)
            db.flush()

        department = db.scalar(select(Department).where(Department.code == "public"))
        if department is None:
            department = Department(code="public", name="Public")
            db.add(department)
            db.flush()

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name="Admin User",
                password_hash=get_password_hash(password),
                role_id=role.id,
                department_id=department.id,
                is_active=True,
            )
            db.add(user)
        else:
            user.password_hash = get_password_hash(password)
            user.role_id = role.id
            user.department_id = department.id
            user.is_active = True
        db.commit()
    finally:
        db.close()


def test_admin_and_bilingual_admin_can_read_permission_matrix(client):
    _ensure_admin_user()
    for email in ["admin@example.local", "bilingual_admin@example.local"]:
        token = _login(client, email)
        response = client.get(
            "/api/v1/admin/permission-matrix",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, {"email": email, "body": response.text}


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
    for forbidden in ["password", "password_hash", "secret", "jwt", "access_token", "token_type"]:
        assert forbidden not in serialized
