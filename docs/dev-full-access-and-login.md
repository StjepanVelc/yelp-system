# Local Development Access & Operational Notes

This document centralizes the local development workflow, service access URLs, authentication defaults, and CDC smoke-test procedures for the Yelp microservices platform.

It also documents the recommended operational flow for starting, stopping, and validating the local stack during development and testing.

## Service URLs

### Core Services

* Frontend: `http://localhost:3000`
* API Gateway: `http://localhost:8000`
* Business Service: `http://localhost:8001`
* Recommendation Service: `http://localhost:8002`
* Ingestion Service: `http://localhost:8003`

### Observability Stack

* Prometheus: `http://localhost:9090`
* Jaeger UI: `http://localhost:16686`
* Grafana: `http://localhost:3001`

---

## CDC Infrastructure

### CDC / Kafka / Debezium Access

* Debezium Connect API: `http://localhost:8083`
* Kafka broker: `localhost:29092`
* CDC Consumer: background worker (no HTTP endpoint)

### Quick CDC Health Checks

```powershell
docker compose ps
docker compose logs debezium-connect --tail=120
docker compose logs cdc-consumer --tail=120
```

---

## Authentication Defaults

### Grafana

Default local credentials:

* Username: `admin`
* Password: `admin`

Notes:

The compose setup uses fallback defaults:

```env
GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
```

If custom values are defined in `.env`, those values override the defaults.

---

### Prometheus

Local development mode does not require authentication.

Health endpoint:

```text
http://localhost:9090/-/ready
```

---

### Jaeger

Local development mode does not require authentication.

---

# Local Stack Management

## Start Full Development Stack

Run from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev-full.ps1 -Action start
```

This command:

* ensures PostgreSQL and Redis are running
* starts the observability stack (Prometheus, Jaeger, Grafana)
* starts local services
* waits for health endpoints before completion

---

## Stack Status

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev-full.ps1 -Action status
```

---

## Stop Stack

Primary shutdown command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev-full.ps1 -Action stop
```

If the state file is unavailable, stop services directly:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\local-dev.ps1 -Action stop

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\observability-local.ps1 -Action stop
```

---

## Restart Stack

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev-full.ps1 -Action restart
```

---

# CDC Smoke Testing (Phase 3)

For CDC invalidation testing, use the deterministic smoke-test workflow instead of immediate Redis assertions. This avoids false negatives caused by asynchronous propagation timing.

## Run Smoke Test

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cdc-smoke-test.ps1
```

## Skip Stack Bring-Up

If the CDC stack is already running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cdc-smoke-test.ps1 -SkipBringUp
```

## Smoke Test Workflow

The script performs the following steps:

* starts CDC infrastructure (unless `-SkipBringUp` is used)
* registers or updates the Debezium connector
* performs controlled database updates for `businesses` and `reviews`
* waits for Redis invalidation through deterministic polling with timeout validation
* validates invalidation results after async propagation completes

---

## Related Documentation

* `docs/production-hardening-report.md`
* `docs/implementation-plan.md`

---

## Quick Debug Checklist

If the CDC smoke test fails:

```powershell
docker compose ps

docker compose logs debezium-connect --tail=120

docker compose logs cdc-consumer --tail=120

docker compose logs kafka --tail=120
```
