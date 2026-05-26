# API Integration Guide - StarSea Robotics Internal (Demo v0.7.1)

## 1. Document Title
API Integration Guide for StarSea Robotics Co., Ltd. internal technical implementation.

## 2. Applicable Department
Technology Department (`tech-internal`) only.

## 3. Purpose
- Define a consistent integration path for backend services, robot gateways, and enterprise systems.
- Reduce integration defects caused by inconsistent authentication and command semantics.
- Provide technical FAQ, do/don't boundaries, and reusable implementation patterns.

## 4. Scope and Non-Scope
This guide covers:
- API authentication and token handling
- Device pairing endpoints
- Robot command APIs
- Route planning/task dispatch APIs
- Operational reliability patterns

This guide does NOT cover:
- Sales pricing, customer discounting, or channel policy
- HR attendance/performance/salary policies
- Marketing narrative, campaign copy, or exhibition scripts
- Product launch commitments and commercial roadmap promises

## 5. Integration Architecture Overview
Recommended integration flow:
1. Enterprise app authenticates via backend service account.
2. Backend service pairs target robot/session.
3. Backend service submits commands/tasks through API gateway.
4. Client consumes command/task status and telemetry events.
5. Audit log persists request IDs, outcomes, and permission-scoped traces.

Key rule: frontend UI can request actions but cannot own privileged credentials.

## 6. Authentication and Authorization
### 6.1 Token strategy
- Use short-lived access tokens for command-time actions.
- Use refresh flow only on trusted backend components.
- Keep per-environment credential separation (dev/staging/prod).

### 6.2 Permission boundary
- API permission is validated server-side by deterministic RBAC/ACL.
- Callers can narrow scope but cannot expand `allowed_kb_ids` or command scope by client parameters.
- Unauthorized calls must return explicit denial responses without disclosing internal details.

### 6.3 Credential safety rules
- Store secrets in managed environment variables or secret manager.
- Never ship secrets in mobile/web bundles.
- Rotate keys and token issuers on a regular schedule.

## 7. Device Pairing API Workflow
### 7.1 Typical endpoints
- `POST /device/pairing/challenge`
- `POST /device/pairing/verify`
- `POST /device/session/heartbeat`
- `POST /device/session/release`

### 7.2 Pairing contract
Required fields usually include:
- `robot_id`
- `gateway_id`
- `signed_nonce`
- `firmware_version`
- `capability_hash`

### 7.3 Validation outcomes
- `paired`: session established
- `rejected_unregistered_device`: unknown robot registry
- `rejected_signature`: invalid signature proof
- `rejected_token_scope`: service account scope mismatch

## 8. Robot Command APIs
### 8.1 Command categories
- Motion: navigate, stop, return-to-dock
- Interaction: speak, display, greet profile
- Delivery: assign package, start route, confirm handoff
- Inspection: start patrol, submit anomaly snapshot

### 8.2 Request pattern
Each command request should include:
- `request_id` (idempotency key)
- `robot_id`
- `command`
- `arguments`
- `safety_profile`
- `issued_by` (service identity)

### 8.3 Response pattern
- Immediate response: request accepted/denied
- Deferred status: queued/executing/success/failure/cancelled
- Error payload: code + user-safe message + operation hint

### 8.4 Idempotency and retries
- Reuse same `request_id` for retry of the same logical action.
- Apply exponential backoff and jitter on transient failures.
- Do not retry non-idempotent actions blindly.

## 9. Route Planning and Task Dispatch APIs
### 9.1 Route planning input
- Start and destination points
- Allowed zone policy
- Time window / priority
- Robot capability requirement

### 9.2 Dispatch lifecycle
1. Validate route request.
2. Check resource locks and zone policy.
3. Select robot candidate by battery/capability/state.
4. Commit dispatch plan and return task ID.
5. Stream task events until completion.

### 9.3 Dispatch failure examples
- `route_blocked`: no available safe route
- `robot_unavailable`: no robot meets constraints
- `policy_rejected`: scope/policy mismatch
- `task_timeout`: execution exceeded SLA window

## 10. Deployment Checklist for Integrators
Before go-live in a site environment:
- Confirm API base URL and TLS trust chain.
- Verify service account role and permission scope.
- Validate robot registry IDs and firmware compatibility.
- Run pairing smoke tests for at least two robots.
- Execute command lifecycle tests (success, cancel, failure).
- Validate telemetry ingestion and alerting pipeline.
- Confirm audit logs include request IDs and outcome states.

## 11. Troubleshooting Quick Map
- 401/403 spikes: token expiration or permission misconfiguration.
- Pairing stuck at challenge: signature mismatch or clock drift.
- Commands accepted but never execute: queue backlog or robot offline.
- Task failures with policy errors: zone policy mismatch or safety profile violation.
- Telemetry gaps: gateway packet loss or stream consumer backpressure.

## 12. Roles and Responsibilities
- API Engineer: maintain contracts/versioning/error model.
- Integration Engineer: build adapters and orchestrations.
- Site Engineer: verify environment/network/device readiness.
- QA Engineer: validate regression, retry behavior, and denial paths.

## 13. FAQ
Q1: Can integration directly skip pairing and invoke commands?
A1: No. Commands depend on valid active session context.

Q2: Can one service account be shared across all environments?
A2: Not recommended. Keep strict environment separation.

Q3: Should API denial reasons include internal implementation details?
A3: No. Return operator-safe messages only.

## 14. Prohibited Actions / Permission Boundaries
- Do not expose device keys or backend secrets to non-technical users.
- Do not bypass authorization by client-side filtering assumptions.
- Do not use technical APIs to derive sales, HR, pricing, or internal roadmap data.

## 15. Example Scenario
A campus deployment backend receives a visitor guidance request, validates token scope, confirms robot session via pairing heartbeat, issues `navigate` command, tracks execution events, and stores an audit trace with request ID.

## 16. RAG-Ready Explicit Fact Points
- Pairing lifecycle: challenge -> verify -> heartbeat -> release.
- Command API must use `request_id` for idempotency.
- Dispatch can fail with `route_blocked`, `robot_unavailable`, `policy_rejected`, or `task_timeout`.
- RBAC/ACL are backend-enforced; client cannot expand permission scope.
- Non-technical departmental data is out of technical API guide scope.
