# Project Status

Last updated: 2026-05-25

## Version Snapshot

- Latest completed implementation version: `v0.4.0`.
- Current documentation track: `v0.4.1 GitHub Presentation Polish` (documentation-only update).

## Current Capabilities

- React + TypeScript + Vite + Tailwind frontend with Knowledge Chat, Knowledge Base/Document/Chunk Viewer, Developer Trace, and GraphRAG page.
- FastAPI backend with JWT authentication, RBAC, and knowledge-base ACL.
- Bilingual department knowledge isolation with deterministic backend permission scope (`allowed_kb_ids`).
- Permission-scoped retrieval with PostgreSQL + pgvector SQL path and safe fallback path.
- Redis permission-aware cache keys and KB-version-based invalidation.
- Markdown/TXT document upload and re-indexing workflow.
- Ollama local router for lightweight classification only.
- Backend-controlled function calling trace and retrieval trace endpoints.
- Neo4j GraphRAG visualization endpoints (status/overview/request graph) with permission scope enforcement.
- Audit logging for QA requests and ingestion actions.

## Test Status

- Baseline validation for `v0.4.0` includes:
  - frontend build (`npm run build`),
  - backend pytest suite,
  - permission matrix script for cross-role validation.
- This `v0.4.1` update changes documentation only (`README.md`, `docs/PROJECT_STATUS.md`), with no backend/frontend business logic changes.

## Known Limitations

- Final answer generation defaults to `LLM_MODE=mock`.
- Ollama is used only as local router/classifier, not as final answer generator.
- Upload/ingestion currently supports Markdown/TXT only.
- PDF/DOCX ingestion is not implemented yet.
- MCP integration is not implemented yet.
- Alembic migrations are planned and not yet added.
- Production hardening (security/ops/reliability) is planned, not completed.
- Repository target is local runnable MVP and engineering showcase, not hosted SaaS.

## Next Roadmap

- Add GitHub Actions CI.
- Integrate a real embedding model.
- Integrate a real LLM answer generator.
- Add PDF/DOCX ingestion pipeline.
- Build user/role/permission admin panel.
- Continue production hardening.
- Add MCP adapter.
