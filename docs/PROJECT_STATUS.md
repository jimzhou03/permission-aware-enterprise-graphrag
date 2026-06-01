# Project Status

Last updated: 2026-06-01

## Current Version

`v0.9.4 demo-ready portfolio version`

This repository is a local reproducible permission-aware RAG / light GraphRAG demo. It is intended for portfolio review, engineering walkthroughs, and local validation of the permission boundary. Do not claim production readiness.

## Implemented

- JWT login and demo accounts.
- RBAC / ACL.
- Pre-filtering RAG.
- `selected_kb_ids = allowed_kb_ids ∩ target_kb_codes` after router targets are resolved to knowledge-base IDs.
- PostgreSQL + pgvector retrieval.
- Redis cache.
- Neo4j light graph projection.
- Developer Trace.
- Audit logs.
- Read-only Permission Matrix Visualizer.
- Fictional department knowledge coverage.
- Docker Compose local demo.
- pytest and permission matrix tests.

## Demo-Level Only

- Mock LLM by default.
- Mock embedding by default.
- Rule-based router by default.
- Fictional seed documents.
- Local Docker Compose.

## Not Implemented

- Production permission admin panel.
- Enterprise SSO.
- Production secret management.
- Production-grade entity disambiguation.
- Community detection.
- Real-time permission propagation control plane.
- Full multi-tenant SaaS backend.
- Production monitoring/alerting.

## Validation Snapshot

The latest v0.9.4 validation state recorded for this demo track:

- pytest: 80 passed, 1 skipped.
- permission matrix: 11/11 PASS.
- demo-check: passed.
- `npm run build`: success.

Re-run these checks before release tagging or public publication if the code changes after this document update.
