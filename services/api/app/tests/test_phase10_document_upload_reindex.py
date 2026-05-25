from app.core.config import get_settings


settings = get_settings()


def _login(client, email: str, password: str = "Passw0rd!123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _knowledge_base_by_code(client, token: str, code: str) -> dict:
    response = client.get("/api/v1/knowledge-bases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    for item in response.json():
        if item["code"] == code:
            return item
    raise AssertionError(f"knowledge base not found: {code}")


def test_bilingual_admin_can_upload_md_and_view_document_and_chunks(client):
    token = _login(client, "bilingual_admin@example.local")
    kb = _knowledge_base_by_code(client, token, "cn-public")
    before_version = kb["version"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Upload Smoke CN Public"},
        files={"file": ("upload-smoke.md", b"# Upload Smoke\n\nPolicy line A.\n\nPolicy line B.", "text/markdown")},
    )
    assert upload_response.status_code == 200, upload_response.text
    upload_payload = upload_response.json()
    assert upload_payload["action"] == "document_upload"
    assert upload_payload["status"] == "success"
    assert upload_payload["knowledge_base_code"] == "cn-public"
    assert upload_payload["chunk_count"] > 0
    assert upload_payload["knowledge_base_version"] >= before_version + 1

    documents_response = client.get(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert documents_response.status_code == 200, documents_response.text
    documents = documents_response.json()
    uploaded_doc = next(item for item in documents if item["id"] == upload_payload["document_id"])
    assert uploaded_doc["title"] == "Upload Smoke CN Public"
    assert uploaded_doc["chunk_count"] == upload_payload["chunk_count"]

    chunks_response = client.get(
        f"/api/v1/documents/{upload_payload['document_id']}/chunks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chunks_response.status_code == 200, chunks_response.text
    chunks = chunks_response.json()
    assert chunks
    assert all(item["has_embedding"] for item in chunks)
    assert all(item["embedding_dimension"] == settings.embedding_dimensions for item in chunks)

    kb_after = _knowledge_base_by_code(client, token, "cn-public")
    assert kb_after["version"] >= before_version + 1


def test_cn_staff_cannot_upload_even_in_allowed_read_scope(client):
    token = _login(client, "cn_staff@example.local")
    kb = _knowledge_base_by_code(client, token, "cn-public")
    response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("blocked.md", b"# blocked", "text/markdown")},
    )
    assert response.status_code == 403, response.text


def test_visitor_cannot_upload(client):
    token = _login(client, "visitor@example.local")
    kb = _knowledge_base_by_code(client, token, "public-policy")
    response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("visitor.md", b"# blocked", "text/markdown")},
    )
    assert response.status_code == 403, response.text


def test_upload_rejects_unsupported_file_types(client):
    token = _login(client, "bilingual_admin@example.local")
    kb = _knowledge_base_by_code(client, token, "cn-public")
    response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("not-supported.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 415, response.text


def test_upload_rejects_oversized_payload(client):
    token = _login(client, "bilingual_admin@example.local")
    kb = _knowledge_base_by_code(client, token, "cn-public")
    oversized_payload = b"A" * (settings.upload_max_size_bytes + 1)
    response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("oversized.txt", oversized_payload, "text/plain")},
    )
    assert response.status_code == 413, response.text


def test_visitor_cannot_view_uploaded_internal_document_chunks(client):
    admin_token = _login(client, "bilingual_admin@example.local")
    visitor_token = _login(client, "visitor@example.local")
    kb = _knowledge_base_by_code(client, admin_token, "cn-internal")

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("cn-internal-upload.md", b"# Internal\n\nConfidential onboarding process.", "text/markdown")},
    )
    assert upload_response.status_code == 200, upload_response.text
    document_id = upload_response.json()["document_id"]

    forbidden_read = client.get(
        f"/api/v1/documents/{document_id}/chunks",
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    assert forbidden_read.status_code == 403, forbidden_read.text


def test_reindex_endpoint_rebuilds_chunks_and_updates_versions(client):
    token = _login(client, "bilingual_admin@example.local")
    kb = _knowledge_base_by_code(client, token, "en-public")

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("en-public-reindex.md", b"# Reindex\n\nLine A.\n\nLine B.\n\nLine C.", "text/markdown")},
    )
    assert upload_response.status_code == 200, upload_response.text
    upload_payload = upload_response.json()
    document_id = upload_payload["document_id"]
    old_doc_version = upload_payload["document_version"]
    old_kb_version = upload_payload["knowledge_base_version"]

    reindex_response = client.post(
        f"/api/v1/documents/{document_id}/reindex",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reindex_response.status_code == 200, reindex_response.text
    reindex_payload = reindex_response.json()
    assert reindex_payload["action"] == "document_reindex"
    assert reindex_payload["status"] == "success"
    assert reindex_payload["document_id"] == document_id
    assert reindex_payload["document_version"] == old_doc_version + 1
    assert reindex_payload["knowledge_base_version"] >= old_kb_version + 1
    assert reindex_payload["chunk_count"] > 0

    chunks_response = client.get(
        f"/api/v1/documents/{document_id}/chunks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chunks_response.status_code == 200, chunks_response.text
    chunks = chunks_response.json()
    assert chunks
    assert all(item["has_embedding"] for item in chunks)
