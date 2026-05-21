# Redis Cache — Runbook & Alerting Policy

Operational reference for the Redis cache layer. Covers incident procedures, alert thresholds, rollout mechanics, and rollback steps.

Document boundary:

- operational response, troubleshooting, and rollback
- alerting policy and on-call actions
- not a cache key/TTL contract document (see `docs/redis-cache.md`)

---

## Alerting Policy

| Alert | Condition | Severity | Response |
|---|---|---|---|
| **Hit-rate drop** | Global hit-rate < 30% for 5+ min after warm-up | Warning | Check `CACHE_ROLLOUT_PERCENT`, Redis memory, recent deployments |
| **Continuous evictions** | Redis `evicted_keys` counter growing continuously | Warning | Expand Redis memory limit or trim TTLs; see Capacity section |
| **Memory high** | Redis memory usage > 80% of `maxmemory` | Warning | Review eviction policy, hot key distribution |
| **Memory critical** | Redis memory usage > 90% | Critical | Disable cache immediately (`REDIS_ENABLED=false`), page on-call |
| **Latency spike** | `cache_latency_ms` p95 > 50ms for 2+ min | Warning | Check Redis CPU, network, connection pool saturation |
| **Redis unreachable** | `cache_initialized enabled=false reason=redis_unreachable` in logs | Critical | Services continue via DB (fail-open). Restore Redis ASAP; monitor DB QPS |
| **Stampede spike** | `cache_shadow namespace=* stampede_waits` rising | Info | Investigate hot key expiry pattern; consider extending TTL or pre-warming |

Check alert state via `GET /cache/stats` on each service.

---

## Observability

### Per-service stats endpoint

```
GET http://localhost:8001/cache/stats   # business-service
GET http://localhost:8002/cache/stats   # recommendation-service
GET http://localhost:8003/cache/stats   # ingestion-service invalidation stats
```

**Response shape:**

```json
{
  "namespaces": {
    "business.details": {
      "hits": 412,
      "misses": 38,
      "errors": 0,
      "hit_rate": 0.9156,
      "locks_acquired": 12,
      "stampede_waits": 3,
      "latency_samples": 450,
      "cache_latency_ms_total": 824.5,
      "cache_latency_ms_avg": 1.83,
      "invalidations": 2,
      "invalidated_keys": 17
    }
  },
  "total": {
    "hits": 500,
    "misses": 50,
    "errors": 0,
    "hit_rate": 0.9090,
    "latency_samples": 550,
    "cache_latency_ms_total": 1001.2,
    "cache_latency_ms_avg": 1.82,
    "invalidations": 2,
    "invalidated_keys": 17
  }
}
```

**Key log events** (search in service logs):

| Event | Meaning |
|---|---|
| `cache_hit` | Served from Redis |
| `cache_miss` | Redis miss, fell through to DB/gRPC |
| `cache_set` | Populated Redis after DB fetch |
| `cache_get_failed` | Redis error on read (fail-open triggered) |
| `cache_set_failed` | Redis error on write (data still returned) |
| `cache_lock_acquire_failed` | Lock contention (normal under load) |
| `cache_shadow` | Shadow mode: `cache_match=True/False` logged per request |
| `cache_invalidation` | Pattern deleted after ingest write |

For ingestion-service, the `/cache/stats` payload is invalidation-focused and reports `invalidations`, `invalidated_keys`, and `errors` per namespace.

---

## Rollout Mechanics

The cache uses two env-var controls that can be changed without a code deployment (restart required):

| Variable | Values | Effect |
|---|---|---|
| `CACHE_ROLLOUT_PERCENT` | `0` – `100` | Deterministic per-entity bucket routing. `0` = cache off. `100` = full rollout (default). |
| `CACHE_SHADOW_MODE` | `true` / `false` | Serve all reads from DB; read Redis and log match/mismatch. Never serves stale data. |

### Recommended rollout sequence

```
Shadow mode (CACHE_SHADOW_MODE=true, ROLLOUT_PERCENT=100)
  → Validate cache_match rate in logs for 24h
  → Target: >99% match rate

Shadow off, canary (ROLLOUT_PERCENT=5)
  → Monitor hit-rate, error-rate, p95 latency for 1h

Expand to 25%  → 50% → 100%
  → Gate: error-rate stable, p95 not regressing, DB QPS trending down
```

### Bucket assignment

`bucket = md5(entity_id) % 100`

Deterministic: the same `business_id` always routes to the same bucket. This makes cache behaviour reproducible across restarts.

---

## Incident Procedures

### Redis Unreachable

**Symptoms:** `cache_initialized enabled=false reason=redis_unreachable` on service startup; API returns 200 (fail-open).

**Steps:**
1. Confirm Redis container is running: `docker compose ps redis`
2. Check Redis logs: `docker compose logs redis --tail=50`
3. Restart if crashed: `docker compose restart redis`
4. Services will reconnect on next request (fail-open until then — DB absorbs load)
5. After restore, monitor `cache_miss` rate; it will be high until warmed up (normal)

**Do NOT** redeploy services to fix a Redis outage — fail-open is working as designed.

---

### Memory Pressure / Evictions

**Symptoms:** `evicted_keys` in Redis INFO growing; `cache_miss` rate rising unexpectedly.

**Steps:**
1. Check Redis memory: `docker compose exec redis redis-cli INFO memory`
2. Check hot keys: `docker compose exec redis redis-cli --hotkeys`
3. If eviction is continuous, raise `maxmemory` in Redis config or lower TTLs
4. Current eviction policy: `allkeys-lru` (or `volatile-lru` if explicit TTLs set)
5. If memory unavailable, set `CACHE_ROLLOUT_PERCENT=0` to stop cache writes

---

### Stale Data Concern

**Symptoms:** User reports seeing old business details after an update.

**Steps:**
1. Check if ingest invalidation ran: search logs for `cache_invalidation namespace=business.details`
2. Manual invalidation: `docker compose exec redis redis-cli DEL <key>` or use pattern delete
3. If urgent: set `CACHE_SHADOW_MODE=true` to stop serving cached reads immediately without downtime
4. Max stale window: details TTL (60m) — data is guaranteed fresh within 60 minutes even without explicit invalidation

---

### CDC Connector / Consumer Troubleshooting

Use this flow when Redis invalidation via Debezium/Kafka is not happening.

**Symptoms:** cache keys stay present after DB write, or no `cache_invalidation*` events in `cdc-consumer` logs.

**Steps:**
1. Check CDC stack status:
  - `docker compose ps db zookeeper kafka debezium-connect cdc-consumer redis`
2. Check Debezium connector status:
  - `curl http://localhost:8083/connectors/yelp-postgres-connector/status`
  - expected: connector `RUNNING`, task `0` `RUNNING`
3. If connector is missing/failed, re-apply config:
  - `./scripts/register-debezium-connector.ps1`
4. Check topic availability:
  - `docker compose exec kafka kafka-topics --bootstrap-server kafka:9092 --list`
  - expected topics include `yelp.public.businesses` and `yelp.public.reviews`
5. Check consumer logs for parsed events and invalidation:
  - `docker compose logs cdc-consumer --tail=200`
  - expected: `cache_invalidation` / `cache_invalidation_pattern`
6. Run deterministic end-to-end smoke test:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/cdc-smoke-test.ps1 -SkipBringUp`

**Notes:**
- CDC is asynchronous; immediate Redis checks right after SQL write can be false negatives.
- Treat smoke test result + consumer invalidation logs as source of truth.

---

### Cache Stampede Detected

**Symptoms:** `stampede_waits` counter rising on `/cache/stats`; elevated lock contention in logs.

**Steps:**
1. This is expected behaviour — the lock prevents thundering herd on hot key expiry
2. If wait count is very high, the lock lease (5s) may be too short for slow DB queries
3. Check DB query latency for `business.details` — if p95 > 5s, increase `_LOCK_LEASE_SECONDS`
4. Consider pre-warming hot keys before TTL expiry.

---

## Rollback Steps

### Disable cache layer entirely (no restart needed... wait, restart required)

```env
REDIS_ENABLED=false
```

Restart services. All reads go directly to DB/gRPC. Zero code change.

### Partial rollback (reduce exposure)

```env
CACHE_ROLLOUT_PERCENT=0
```

Restart services. Cache layer code stays loaded but no request is routed through it.

### Shadow mode (validate without serving)

```env
CACHE_SHADOW_MODE=true
```

Restart services. All reads from DB; Redis reads happen in background for comparison only.

---

## Capacity Reference

| Namespace | Avg payload | Max keys | Est. memory |
|---|---|---|---|
| `business.details` | ~2 KB | 150,346 (all businesses) | ~300 MB worst-case |
| `recommendation.by_business` | ~4 KB | 150,346 × typical limits | ~600 MB worst-case |
| `business.cities` | ~1 KB | 1 key | negligible |

In practice, working set is much smaller (LRU eviction). A 256–512 MB Redis instance covers normal load comfortably.

**Eviction policy recommendation:** `allkeys-lru` — evicts least-recently-used keys across all namespaces when memory is full. Correct for this workload (no explicit persistence requirement).

---

## Owner / Escalation

| Role | Responsibility |
|---|---|
| On-call backend | Redis outage, memory pressure, stale data reports |
| System owner | Rollout gates, TTL/eviction policy changes, capacity upgrades |

---

## Security Baseline

Redis requires a password (`requirepass`) set via the `REDIS_PASSWORD` env var.

**Dev default:** `REDIS_PASSWORD=dev_redis_pass`  
**Production:** set a strong random password; rotate every 90 days.

Connect from host:
```bash
redis-cli -h localhost -p 6379 -a "$REDIS_PASSWORD"
```

Connect from inside Docker network:
```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD"
```

**ACL (next step for production):**
Create a read-only ACL for cache consumer services and a write ACL for the ingestion
service. Use `ACL SETUSER` or an `acl.conf` mounted into the container.

---

## Backup & Restore

### Data persistence configuration
| Mechanism | Config | Purpose |
|---|---|---|
| **AOF** | `--appendonly yes` | Write-ahead log; crash-safe, minimal data loss |
| **RDB** | `--save 3600 1 --save 300 100 --save 60 10000` | Point-in-time snapshots; compact, fast restore |
| **Volume** | `redis_data:/data` | Persists both AOF and RDB across container restarts |

### Restore from RDB backup
```bash
# 1. Stop Redis
docker compose stop redis

# 2. Copy your dump.rdb into the Docker volume
#    Find volume path:
docker volume inspect yelp-system_redis_data
#    Copy file to the Mountpoint shown above:
cp /path/to/backup/dump.rdb /var/lib/docker/volumes/yelp-system_redis_data/_data/dump.rdb

# 3. Restart Redis (will load dump.rdb on startup)
docker compose start redis

# 4. Verify
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" DBSIZE
```

### Manual cache warm-start after restore
After restoring from backup, services will serve from the restored cache immediately.
If the backup is stale, prefer wiping the cache and re-warming:
```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" FLUSHALL
# Then send a burst of requests to warm up the cache
python scripts/cache_load_test.py load --rounds 5
```
