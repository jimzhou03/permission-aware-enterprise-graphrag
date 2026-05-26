# Robot SDK Manual

This document is fictional and used for local demo only.

## SDK Access Basics

- Internal teams use `robot-sdk` package for command and telemetry abstraction.
- Every integration project must register a `project_id` and `client_key`.
- Production key rotation is handled by the platform team, not by frontend clients.

## Message Topics

- `robot.command.dispatch` for action commands.
- `robot.status.report` for heartbeat and runtime state.
- `robot.alert.event` for hardware or safety alerts.

## Safe Integration Rules

- Never bypass backend permission checks when mapping user actions to SDK commands.
- Do not expose internal tokens in browser runtime.
- Log integration errors with correlation ids for audit trace.
