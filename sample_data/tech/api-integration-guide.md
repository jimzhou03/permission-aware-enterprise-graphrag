# API Integration Guide

This document is fictional and used for local demo only.

## Integration Flow

1. Authenticate user identity by backend JWT endpoint.
2. Resolve allowed knowledge bases by backend RBAC/ACL.
3. Call `/qa/ask` with optional scoped knowledge base codes.
4. Render answer summary and source snippets in product UI.

## Error Handling

- `401`: user not authenticated.
- `403`: request is outside allowed permission scope.
- `422`: request payload validation error.

## Security Notes

- Frontend controls only display scope; permission scope is backend-enforced.
- Unauthorized chunks must not appear in answer, trace, cache, or graph views.
