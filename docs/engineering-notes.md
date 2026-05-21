# Engineering Notes

## Purpose

This document is the consolidated engineering record for implementation, debugging, and operational decisions made during the recent platform upgrade cycle. It replaces fragmented phase and personal log notes with a single professional reference.

Document boundary:

- debugging timeline and technical incidents
- root causes, remediation decisions, and lessons learned
- not the canonical source for final completion status (see production hardening report)

## Scope Covered

The notes below summarize implementation and validation work across:

- observability baseline and diagnostics workflow
- cache hardening and operational controls
- CDC-enabled cache invalidation (Debezium + Kafka)
- local performance investigation and latency remediation
- load-testing tooling and development quality-of-life improvements

## Key Engineering Workstreams

### Frontend Search Flow and Debug Controls

Implemented end-to-end frontend search flow support, including URL query propagation, API forwarding, and development-only controls for search-path testing. This improved request-path visibility from browser to gateway and downstream services.

### Logging, Tracing, and Runtime Consistency

An early startup issue was caused by a Protobuf/gRPC version mismatch between generated stubs and Docker runtime dependencies.

Actions taken:

- aligned generated gRPC artifacts with runtime package versions
- rebuilt and restarted the stack after dependency alignment
- verified stable startup across affected services

Lesson learned: generated artifacts and runtime libraries must be version-compatible across local and containerized environments.

### PostgreSQL Configuration Reliability

Resolved recurring database connection failures caused by environment/config drift.

Actions taken:

- corrected database URL and service-level connection settings
- separated local and container runtime configuration concerns
- clarified environment variable structure to reduce ambiguity

Lesson learned: many database incidents are configuration faults, not application logic defects.

### Local vs Docker Runtime Separation

Investigations identified mixed local and containerized service execution as a recurring source of false diagnostics (for example, one service local, others in Docker).

Actions taken:

- verified active services and port ownership before testing
- standardized test sessions to one runtime mode at a time
- restarted the intended stack before latency or logic analysis

Lesson learned: validate runtime topology before debugging business logic.

### Docker gRPC Networking

Resolved inter-service connectivity issues caused by incorrect host addressing from within containers.

Actions taken:

- replaced localhost assumptions with Docker service DNS names
- moved gRPC host/port values to environment-driven configuration
- validated container-to-container communication path

Lesson learned: inside Docker, localhost resolves to the current container, not peer services.

### Full-Text Search Prerequisites

Addressed failures caused by missing database-side FTS prerequisites.

Actions taken:

- added migration for `search_vector`, trigger logic, and index support
- backfilled existing rows
- preserved fallback search path behavior when FTS is incomplete

Lesson learned: application features depending on DB-generated structures require strict migration order discipline.

## Latency Investigation and Resolution

### Incident Summary

A significant local latency issue was traced to Windows localhost name resolution behavior. Requests routed through `localhost` incurred an approximately 2-second pre-application delay, while equivalent loopback requests to `127.0.0.1` completed in tens of milliseconds.

### Why It Was Misleading

The delay affected both direct service calls and gateway-proxied calls, which initially suggested bottlenecks in authentication, cache, database, or proxy layers.

### Investigation Method

- collected baseline latency samples for gateway and direct endpoints
- compared direct measurements on `localhost` versus `127.0.0.1`
- validated service health and ruled out major query-path regressions
- repeated tests after local URL normalization

### Root Cause

Windows localhost resolution/fallback path introduced a fixed network delay before requests reached application logic.

### Remediation

- switched local development/test URLs to `127.0.0.1`
- kept Docker internal service addressing unchanged
- re-ran benchmarks to establish corrected baseline

### Before / After Snapshot

Before (localhost-based tests):

- gateway endpoints: approximately 3.2-3.5 s
- direct service endpoints: approximately 2.0-2.2 s

After (127.0.0.1-based tests):

- direct service endpoints: approximately 15-20 ms
- gateway endpoints: approximately 10-15 ms

### Conclusion

The major latency defect was environmental (hostname resolution), not business logic. Baseline performance for local development returned to expected millisecond ranges after loopback normalization.

## Additional Operational Deliverables

### Live Traffic Dashboard

Implemented an interactive dashboard tool for local traffic generation and live KPI visualization, with export support for charts and full HTML snapshots.

Primary script:

- `scripts/traffic_dashboard.py`

### Live Monitor and Static Reporting

Implemented a terminal-based monitor that streams metrics and writes report artifacts (including HTML output) to test-results directories.

Primary script:

- `scripts/traffic_live_monitor.py`

### LAN Testing Guide

Documented host/client setup, LAN URL checks, firewall prerequisites, and troubleshooting for two-machine test sessions.

Primary document:

- `docs/testing-lan.md`

### Gateway Development Fail-Open for User Status

Added controlled development behavior to avoid non-critical local blocking when user-status service is intentionally absent.

Primary module:

- `services/api-gateway/app/clients/user_status_client.py`

## Engineering Principles Reinforced

- Validate infrastructure and runtime topology before optimizing application code.
- Keep local and container configurations explicit and separated.
- Treat observability as a core capability, not a post-incident add-on.
- Require deterministic, repeatable test paths for performance and reliability conclusions.
- Maintain one canonical documentation source to reduce drift and contradictory guidance.

## Notes

For final completion status and delivered scope summary, use `docs/production-hardening-report.md`.
