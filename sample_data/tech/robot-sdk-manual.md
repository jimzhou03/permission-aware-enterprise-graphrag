# Robot SDK Manual - StarSea Robotics Internal (Demo v0.7.1)

## 1. Document Title
Robot SDK Manual for StarSea Robotics Co., Ltd. internal technical teams.

## 2. Applicable Department
Technology Department (`tech-internal`) only. This document is intended for software engineers, field integration engineers, QA engineers, and technical support engineers who have technical access approval.

## 3. Purpose
- Provide a stable SDK mental model for integration projects.
- Standardize authentication, device pairing, command invocation, and task life-cycle handling.
- Prevent misuse by clarifying technical scope and non-technical boundaries.

## 4. Technical Scope and Explicit Boundaries
This manual covers technical SDK topics only:
- SDK package structure
- Device authentication and pairing
- Robot command APIs
- Route planning and task dispatch lifecycle
- Telemetry event interpretation

Out of scope (must not be answered from this document):
- Sales pricing strategy and discount policy
- HR policy, attendance, payroll, compensation
- Marketing campaign plan and public messaging wording
- Product launch roadmap approval decisions
- Customer contract pricing or legal commitments

If a request asks for non-technical internal data, redirect to the owning department knowledge base according to RBAC policy.

## 5. SDK Structure
The SDK is organized into layered modules:

1. `core.auth`
- Token lifecycle management
- Device credential validation
- Pairing session signature helpers

2. `core.transport`
- HTTP client wrapper
- Retry and timeout policy
- Error normalization (`NetworkTimeout`, `Unauthorized`, `DeviceOffline`)

3. `robot.session`
- Pairing handshake
- Session heartbeat
- Device capability snapshot

4. `robot.command`
- High-level robot commands such as `navigate`, `stop`, `dock`, `speak`, `pickup`, `dropoff`
- Command acknowledgement and execution-state polling

5. `robot.dispatch`
- Task creation and assignment
- Route segment stitching
- Priority and queue policies

6. `robot.telemetry`
- Device health (`battery`, `motor_status`, `sensor_status`, `network_latency`)
- Event stream adapters for monitoring dashboards

7. `utils.validation`
- Request schema checks
- Safe boundary checks (speed caps, zone restrictions, payload limits)

## 6. Authentication and Device Pairing
### 6.1 Authentication model
The integration client authenticates with backend-issued access tokens. Tokens are scoped by environment, workspace, and service account role.

Minimum requirements:
- Use short-lived access tokens for runtime commands.
- Do not hard-code device keys into frontend code.
- Rotate service credentials on schedule.

### 6.2 Pairing workflow
1. Client requests a pairing challenge from the API gateway.
2. Robot returns signed device proof.
3. Backend verifies signature and device registry state.
4. Pairing session is created with a `session_id` and expiration.
5. Heartbeat starts every fixed interval to keep the session alive.

Pairing failure common causes:
- Device not registered in current environment
- Signature mismatch due to stale key
- Robot clock drift beyond allowed skew
- Token expired before pairing commit

## 7. Robot Command API Patterns
### 7.1 Command submission
Commands should be idempotent. Every command includes:
- `request_id` (client-generated, unique)
- `robot_id`
- `command_type`
- `payload`
- `safety_policy`

Example command categories:
- Navigation: `navigate_to_point`, `follow_route`, `return_to_dock`
- Interaction: `speak_text`, `display_prompt`
- Task operation: `start_delivery`, `confirm_dropoff`, `abort_task`

### 7.2 Acknowledgement and execution states
Typical state sequence:
`accepted -> queued -> executing -> completed` or `failed` / `cancelled`

Engineering guidance:
- Treat `accepted` as queue admission, not task completion.
- Poll status with backoff to avoid API overload.
- Handle cancellation race conditions (task may finish while cancel request is in flight).

### 7.3 Error classes
- `401/403`: auth or permission scope issue
- `404`: unknown robot/task identifier
- `409`: conflicting command or route lock
- `422`: invalid payload or unsafe command boundary
- `503`: control-plane service degradation

## 8. Route Planning and Task Dispatch
### 8.1 Route planning constraints
Route generation considers:
- Zone permissions
- Elevator availability windows
- Dynamic no-go zones
- Speed profile per corridor type

### 8.2 Task dispatch lifecycle
1. Validate task schema and destination.
2. Reserve route resources.
3. Allocate robot by capability and battery threshold.
4. Dispatch task and monitor progress.
5. Close task with outcome code and audit note.

### 8.3 Dispatch policy hints
- High-priority incident tasks can preempt low-priority delivery tasks.
- Preemption must preserve safe stop behavior before route reassignment.
- Re-dispatch attempts should be bounded to avoid infinite retries.

## 9. Roles and Responsibilities
- SDK Developer: maintain API contract and backward compatibility.
- Integration Engineer: implement project-side adapters and validation.
- Field Engineer: verify network, map, and hardware readiness on site.
- QA Engineer: test normal flow, boundary cases, and failure recovery.

## 10. FAQ
Q1: Can we call commands directly from browser clients?
A1: Not recommended. Use backend proxy with scoped credentials.

Q2: Should pairing tokens be reused across environments?
A2: No. Pairing artifacts are environment-scoped.

Q3: How do we handle intermittent connectivity?
A3: Use retry with jitter, idempotent request IDs, and state reconciliation.

## 11. Prohibited Actions / Permission Boundaries
- Do not expose technical tokens, signing keys, or device secrets to non-technical roles.
- Do not use SDK endpoints to infer or leak cross-department business data.
- Do not bypass backend RBAC/ACL with frontend-only filtering.

## 12. Example Scenarios
- Scenario A: A school reception robot is paired, receives a navigation command, and reports completion with telemetry updates.
- Scenario B: A delivery task fails due to blocked corridor; dispatch service retries with an alternate route and records failure reason if retries exhaust.

## 13. RAG-Ready Explicit Fact Points
- SDK modules: `core.auth`, `core.transport`, `robot.session`, `robot.command`, `robot.dispatch`, `robot.telemetry`, `utils.validation`.
- Pairing requires challenge, signed proof, registry validation, and heartbeat.
- Command lifecycle includes `accepted`, `queued`, `executing`, `completed/failed/cancelled`.
- Non-technical scopes (sales/HR/marketing/roadmap/pricing) are explicitly out of technical scope.
- Technical secrets must never be exposed outside authorized technical access.
