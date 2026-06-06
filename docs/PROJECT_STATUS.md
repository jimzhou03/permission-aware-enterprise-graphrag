# Project Status

Last updated: 2026-06-06

## Current Version

`v0.9.5 demo-ready hardening version`

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
- Public ask response hides raw chunk/citation debug fields.
- Developer Trace and document full chunk content are restricted to audit/debug permissions.
- Production configuration guard blocks unsafe demo defaults when `ENVIRONMENT=production`.

## Demo-Level Only

- Mock LLM by default.
- Mock embedding by default.
- Rule-based router by default.
- Fictional seed documents.
- Local Docker Compose.
- Adminer and Redis Commander are debug-profile tools, not production services.

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

The latest v0.9.5 validation state should be refreshed after hardening changes:

- pytest: pending re-run.
- permission matrix: pending re-run.
- demo-check: pending re-run.
- `npm run build`: pending re-run.

Re-run these checks before release tagging or public publication if the code changes after this document update.
