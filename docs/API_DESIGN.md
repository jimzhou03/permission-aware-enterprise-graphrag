# API Design

## 1. API Conventions

- Base URL: `/api/v1`
- Authentication: `Authorization: Bearer <access_token>`
- Request and response format: JSON unless an endpoint explicitly accepts file upload.
- Errors use standard HTTP status codes with structured FastAPI error responses.

This document describes the API surface that exists in the current v0.9.4 demo. Future ideas are listed separately and must not be presented as implemented endpoints.

## 2. Auth API

### POST `/auth/login`

Logs in with a demo account and returns a JWT.

Request:

```json
{
  "email": "product_staff@example.local",
  "password": "Passw0rd!123"
}
```

Response includes:

- `access_token`
- `token_type`
- `user`

### GET `/auth/me`

Returns the current authenticated user, role, department, and permission summary.

## 3. Knowledge Base API

### GET `/knowledge-bases`

Returns only knowledge bases visible to the current authenticated user according to backend RBAC/ACL.

### GET `/knowledge-bases/{kb_id}/documents`

Returns documents for an authorized knowledge base. `{kb_id}` may be the knowledge base UUID or code.

### POST `/knowledge-bases/{kb_id}/documents/upload`

Uploads a Markdown/TXT document into an authorized writable knowledge base.

- Requires authentication.
- Requires the target KB to be in the user's allowed scope.
- Requires backend write permission for that KB.
- This is a demo ingestion path, not a production document governance workflow.

## 4. Document / Chunk API

### GET `/documents/{document_id}/chunks`

Returns chunks for a document only when the current user can access the document's knowledge base.

This endpoint can expose full authorized chunk content for debugging and observability. It does not expose chunks outside the viewer's backend RBAC/ACL scope.

### POST `/documents/{document_id}/reindex`

Reindexes an existing document when the user can access the document's KB and has backend write permission for that KB.

## 5. QA API

### POST `/qa/ask`

Submits a question. The backend resolves the authenticated user's allowed KBs, classifies the requested target scope, computes `selected_kb_ids = allowed_kb_ids ∩ target_kb_codes` after resolving target codes to IDs, and retrieves only within the selected scope.

Request:

```json
{
  "question": "公司内部员工如何申请知识库权限？",
  "mode": "auto",
  "knowledge_base_codes": []
}
```

Response includes:

- `request_id`
- `answer`
- `denied`
- `refusal_reason`
- `cache_hit`
- `mode`
- `route`
- `sources`
- `retrieved_chunks`
- `citations`
- `graph_paths`
- `function_trace_summary`

The normal chat UI hides chunk-level debug fields and displays sanitized sources. The API response may retain authorized `citations` / `retrieved_chunks` for debugging and trace compatibility; these are still scoped by backend RBAC/ACL and selected KB IDs.

### GET `/qa/{request_id}`

Returns a QA audit record for the request owner or a user with `audit:read`.

### GET `/qa/{request_id}/trace`

Returns Developer Trace details for the request owner or a user with `audit:read`.

Trace can reconstruct and expose full authorized chunk content. It filters chunk content by the current viewer's backend permission scope.

### GET `/qa/{request_id}/graph`

Returns graph trace elements for the request owner or a user with `audit:read`.

Graph trace is scoped to the current viewer's backend permission scope and does not expose full chunk content.

## 6. Graph API

### GET `/graph/status`

Returns Neo4j / graph projection status for an authenticated user.

### GET `/graph/overview`

Returns a permission-scoped graph overview for the current authenticated user.

### POST `/graph/sync`

Synchronizes the light Neo4j graph projection.

- Requires `admin:kb:write`.
- This is a demo graph projection sync, not a production graph construction pipeline.

## 7. Admin API

### GET `/admin/audit-logs`

Returns recent QA audit records.

- Requires `audit:read`.

### GET `/admin/permission-matrix`

Returns the read-only permission matrix used by the Permission Matrix Visualizer.

- Requires `admin:users:read`.
- Read-only.
- Does not create users, edit roles, rotate passwords, issue tokens, or expose secrets.
- Does not act as a production permission management backend.

## 8. System API

### GET `/system/retrieval-config`

Returns runtime retrieval, embedding, router, cache, upload, and graph configuration visible to an authenticated user.

## 9. Demo API

### GET `/demo/overreach-cases`

Returns preset demo overreach cases for walkthroughs.

This endpoint is unauthenticated and contains only static demo prompts.

## 10. Permission Summary

| API | Auth | Permission / Scope |
| --- | --- | --- |
| `POST /auth/login` | No | Demo account credentials |
| `GET /auth/me` | Yes | Current user |
| `GET /knowledge-bases` | Yes | Current user's allowed KB scope |
| `GET /knowledge-bases/{kb_id}/documents` | Yes | Authorized KB scope |
| `POST /knowledge-bases/{kb_id}/documents/upload` | Yes | Authorized KB scope + KB write permission |
| `GET /documents/{document_id}/chunks` | Yes | Authorized document KB scope |
| `POST /documents/{document_id}/reindex` | Yes | Authorized document KB scope + KB write permission |
| `POST /qa/ask` | Yes | `qa:ask` |
| `GET /qa/{request_id}` | Yes | Request owner or `audit:read` |
| `GET /qa/{request_id}/trace` | Yes | Request owner or `audit:read` |
| `GET /qa/{request_id}/graph` | Yes | Request owner or `audit:read` |
| `GET /graph/status` | Yes | Current user |
| `GET /graph/overview` | Yes | Current user's allowed KB scope |
| `POST /graph/sync` | Yes | `admin:kb:write` |
| `GET /admin/audit-logs` | Yes | `audit:read` |
| `GET /admin/permission-matrix` | Yes | `admin:users:read` |
| `GET /system/retrieval-config` | Yes | Current user |
| `GET /demo/overreach-cases` | No | Static demo endpoint |

## 11. Future / Not Implemented

The following are not implemented in v0.9.4 and must not be described as current APIs:

- `/admin/users`
- `/admin/documents`
- Production permission admin panel.
- Enterprise SSO.
- Production secret management.
- Sanitized public ask response split.
- Real-time permission propagation control plane.
- Production-grade entity disambiguation.
- Community detection.
- Full production graph construction pipeline.
- MCP adapter.
