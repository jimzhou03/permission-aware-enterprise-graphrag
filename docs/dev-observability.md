# Local Observability Dev Tools (Local Development Only)

This document is for **local development only**.  
These tools are not production admin backends.

## 1) Service Endpoints

- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Neo4j Browser: `http://127.0.0.1:7474`
- Adminer (PostgreSQL UI): `http://127.0.0.1:8081`
- Redis Commander (Redis UI): `http://127.0.0.1:8082`

## 2) PostgreSQL in Adminer (Local Dev Only)

Login fields in Adminer:

- `System`: `PostgreSQL`
- `Server`: `postgres`
- `Username`: read from `infra/.env` or `infra/docker-compose.yml` (`POSTGRES_USER`, default `graphrag`)
- `Password`: read from `infra/.env` or `infra/docker-compose.yml` (`POSTGRES_PASSWORD`, default `graphrag`)
- `Database`: read from `infra/.env` or `infra/docker-compose.yml` (`POSTGRES_DB`, default `graphrag`)

## 3) PostgreSQL Common SQL Queries

Connect with psql:

```bash
cd infra
docker compose exec -T postgres psql -U graphrag -d graphrag
```

List tables:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

List users (application users):

```sql
SELECT
  u.email,
  r.name AS role,
  d.code AS department,
  u.is_active,
  u.created_at
FROM users u
LEFT JOIN roles r ON r.id = u.role_id
LEFT JOIN departments d ON d.id = u.department_id
ORDER BY u.created_at DESC;
```

List knowledge bases:

```sql
SELECT id, code, name, visibility, version, is_active, created_at
FROM knowledge_bases
ORDER BY created_at DESC;
```

List documents:

```sql
SELECT id, knowledge_base_id, title, source_label, version, status, created_at
FROM documents
ORDER BY created_at DESC
LIMIT 100;
```

List chunks (with preview):

```sql
SELECT
  id,
  knowledge_base_id,
  document_id,
  ordinal,
  LEFT(content, 120) AS content_preview,
  created_at
FROM document_chunks
ORDER BY created_at DESC
LIMIT 100;
```

Recent audit logs:

```sql
SELECT
  request_id,
  user_id,
  denied,
  cache_hit,
  mode,
  model,
  latency_ms,
  created_at
FROM qa_audit_logs
ORDER BY created_at DESC
LIMIT 50;
```

Recent QA requests and hit IDs:

```sql
SELECT
  request_id,
  denied,
  hit_kb_ids,
  hit_document_ids,
  hit_chunk_ids,
  created_at
FROM qa_audit_logs
ORDER BY created_at DESC
LIMIT 20;
```

Permission-related ACL inspection:

```sql
SELECT
  kb.code AS kb_code,
  r.name AS role,
  d.code AS department,
  a.access_level,
  a.created_at
FROM knowledge_base_acl a
LEFT JOIN knowledge_bases kb ON kb.id = a.knowledge_base_id
LEFT JOIN roles r ON r.id = a.role_id
LEFT JOIN departments d ON d.id = a.department_id
ORDER BY kb.code, role, department;
```

Role to permission mapping:

```sql
SELECT
  r.name AS role,
  p.code AS permission_code
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
ORDER BY role, permission_code;
```

## 4) Redis UI and CLI (Local Dev Only)

Redis Commander UI:

- URL: `http://127.0.0.1:8082`
- In-container host/port: `redis:6379`
- Runtime use in this project: permission-aware cache, KB version invalidation effect observation, temporary cache inspection

Redis CLI commands:

```bash
cd infra
docker compose exec redis redis-cli KEYS '*'
```

```bash
cd infra
docker compose exec redis redis-cli GET "<key>"
```

```bash
cd infra
docker compose exec redis redis-cli TTL "<key>"
```

Clear local development cache only:

```bash
cd infra
docker compose exec redis redis-cli FLUSHDB
```

## 5) Neo4j Browser and Cypher (Local Dev Only)

Neo4j Browser:

- URL: `http://127.0.0.1:7474`
- Bolt: `bolt://127.0.0.1:7687`
- Username/password: read from `infra/.env` or `infra/docker-compose.yml` (`NEO4J_AUTH`, default `neo4j/password12345`)

All nodes:

```cypher
MATCH (n)
RETURN n
LIMIT 100;
```

All relationships:

```cypher
MATCH ()-[r]->()
RETURN r
LIMIT 100;
```

By label/type:

```cypher
MATCH (kb:KnowledgeBase) RETURN kb LIMIT 50;
```

```cypher
MATCH (doc:Document) RETURN doc LIMIT 50;
```

```cypher
MATCH (c:Chunk) RETURN c LIMIT 50;
```

```cypher
MATCH (e:Entity) RETURN e LIMIT 50;
```

Inspect graph paths for one chunk:

```cypher
MATCH (c:Chunk {id: "<chunk_id>"})-[:MENTIONS]->(e:Entity)
OPTIONAL MATCH (e)-[:RELATED_TO]-(related:Entity)
RETURN c.id AS chunk_id, e.name AS entity, collect(DISTINCT related.name)[0..10] AS related_entities;
```

About request-level path lookup:

- Current graph model does not persist `request_id` as a Neo4j node.
- For request-level analysis, first read `hit_chunk_ids` from `qa_audit_logs` (PostgreSQL), then query those chunk IDs in Neo4j.
- You can also use API trace endpoint: `GET /api/v1/qa/{request_id}/trace`.
