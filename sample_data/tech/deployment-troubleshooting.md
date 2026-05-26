# Deployment Troubleshooting

This document is fictional and used for local demo only.

## Common Issues

- API container not rebuilt after code change.
- Missing environment variables for mock mode toggles.
- Neo4j unavailable causing graph fallback mode.

## Checklist

- Rebuild containers before regression checks.
- Verify `LLM_MODE=mock` and `EMBEDDING_MODE=mock` for demo consistency.
- Validate permission matrix after seed data updates.

## Escalation

- If unauthorized content is observed in any output, stop demo and investigate scope checks.
- If router metadata is stale, restart API and rerun the request trace.
