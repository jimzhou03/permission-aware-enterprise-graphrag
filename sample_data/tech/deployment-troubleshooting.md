# Deployment & Troubleshooting Handbook - StarSea Robotics Internal (Demo v0.7.1)

## 1. Document Title
Deployment and Troubleshooting Handbook for StarSea Robotics technical operations.

## 2. Applicable Department
Technology Department (`tech-internal`) only.

## 3. Purpose
- Provide a practical deployment checklist for new site onboarding.
- Standardize troubleshooting for network, registration, task execution, and sensors.
- Offer safe escalation guidance while preserving access boundaries.

## 4. Technical Scope
This handbook covers technical operation topics only:
- Environment readiness checks
- Device registration and pairing diagnostics
- Task execution path verification
- Sensor and telemetry status triage
- Incident escalation checkpoints

Out of scope:
- Customer pricing discussion
- Sales channel terms
- HR employee policy
- Marketing campaign strategy
- Product commercial roadmap commitments

## 5. Pre-Deployment Checklist
### 5.1 Infrastructure baseline
- API service reachable from target network segment.
- Database/cache dependencies healthy.
- Time synchronization enabled on robot gateways and backend hosts.
- DNS and outbound policies allow required service endpoints.

### 5.2 Identity and access
- Service account role validated for deployment environment.
- Robot registry entries created and active.
- Device credentials issued and version-tagged.
- Rotation policy documented for keys/tokens.

### 5.3 Site readiness
- Map files and no-go zones loaded.
- Elevator/door integration points validated (if required).
- Charging dock coordinates calibrated.
- Safety boundaries and emergency stop procedures confirmed.

### 5.4 Functional dry run
- Pairing success rate >= expected baseline.
- Basic navigation command success.
- At least one delivery or patrol task completed end-to-end.
- Telemetry stream visible in monitoring panel.

## 6. Deployment Workflow
1. Environment sanity check (`healthz`, dependency checks, config snapshot).
2. Register devices and validate registry consistency.
3. Pair robots and keep heartbeat stable.
4. Execute smoke commands in controlled zone.
5. Start staged task dispatch (low-priority first).
6. Enable monitoring and alert thresholds.
7. Capture go-live baseline metrics.

## 7. Troubleshooting by Domain
### 7.1 Network connectivity issues
Symptoms:
- API call timeouts
- Intermittent heartbeat failures
- Telemetry dropouts

Checklist:
- Validate gateway-to-API latency and packet loss.
- Check DNS resolution and proxy policy.
- Confirm firewall allows required ports.
- Inspect retry storm patterns causing self-induced congestion.

Actions:
- Apply backoff/jitter policy.
- Reduce polling frequency temporarily.
- Fail over to local queue buffering if supported.

### 7.2 Device registration and pairing failures
Symptoms:
- Pairing rejected repeatedly
- Session expires immediately

Checklist:
- Robot ID exists and is active in registry.
- Signature key version matches backend record.
- Device clock skew within allowed threshold.
- Token scope permits pairing operation.

Actions:
- Re-issue pairing challenge.
- Rotate device key when signature mismatch persists.
- Sync NTP on gateway and robot controller.

### 7.3 Task execution anomalies
Symptoms:
- Task stays in queued state
- Frequent cancellation/failure outcomes
- Route preemption loops

Checklist:
- Robot availability and battery threshold.
- Route lock conflicts.
- Safety policy mismatch with zone rules.
- Task queue priority inversion.

Actions:
- Trigger queue rebalance.
- Recompute route with updated constraints.
- Apply bounded retries with terminal failure codes.

### 7.4 Sensor status anomalies
Symptoms:
- Obstacle sensor offline
- Localization drift
- False anomaly spikes

Checklist:
- Sensor health endpoint flags.
- Firmware compatibility matrix.
- Calibration timestamp and drift history.
- Environmental interference sources.

Actions:
- Run calibration routine.
- Reset sensor process where allowed.
- Mark robot as limited-capability if critical sensor remains degraded.

## 8. Incident Severity and Escalation
- Severity P1: multiple robots unavailable, critical site impact.
- Severity P2: single robot major function blocked, workaround possible.
- Severity P3: partial degradation, low user impact.

Escalation flow:
1. On-call engineer triages and assigns severity.
2. Capture request IDs, robot IDs, and timeline.
3. Notify platform owner for P1/P2.
4. Publish mitigation status at fixed intervals.
5. Close incident with root-cause summary and prevention actions.

## 9. Roles and Responsibilities
- On-call Engineer: first response and stabilization.
- Platform Engineer: backend/API/root-cause diagnostics.
- Field Engineer: site/network/hardware checks.
- QA Engineer: reproduction validation and regression guard.

## 10. FAQ
Q1: Why does pairing pass but commands still fail?
A1: Pairing validates session identity, but command execution still depends on route/resource/safety checks.

Q2: Should we keep retrying forever when task execution fails?
A2: No. Use bounded retries and clear terminal status to avoid hidden backlog growth.

Q3: Can we expose full internal error traces to non-admin users?
A3: No. Share safe operator messages and keep deep traces in developer/admin channels.

## 11. Prohibited Actions / Permission Boundaries
- Do not share technical keys, secret configs, or raw internal traces outside authorized technical/admin scope.
- Do not bypass backend authorization controls for emergency shortcuts.
- Do not repurpose troubleshooting tools to access unrelated departmental data.

## 12. Example Scenario
A hotel delivery robot reports frequent task timeouts. Investigation finds gateway packet loss and route lock conflicts during elevator windows. Team adjusts polling frequency, applies queue rebalance, and updates route constraints. Timeout rate returns to baseline and incident is closed as P2 resolved.

## 13. RAG-Ready Explicit Fact Points
- Pre-deployment checks include infrastructure, identity, site readiness, and functional dry run.
- Troubleshooting domains: network, pairing/registration, task execution, sensor status.
- Pairing failures commonly relate to registry state, key mismatch, clock skew, token scope.
- Incident severities use P1/P2/P3 with explicit escalation flow.
- Non-technical topics (sales/HR/marketing/roadmap/pricing) are out of scope.
