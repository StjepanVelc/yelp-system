# Redis Cache — Contract & Design Reference

## Cached Endpoints

Cache-aside pattern covers three read routes:

- `GET /businesses/{id}` — business details
- `GET /businesses/cities` — cities list
- `GET /recommendations/{id}?limit=` — recommendations

Write-through invalidation fires after successful ingest commits for businesses, reviews, and users.

## Cache Key Format

```
yelp:{env}:{domain}:{resource}:{id_or_hash}:v{schema}
```

Active keys:

| Key | Example |
|---|---|
| Business details | `yelp:prod:business:details:{business_id}:v1` |
| Cities list | `yelp:prod:business:cities:all:v1` |
| Recommendations | `yelp:prod:recommendation:by_business:{business_id}:{limit}:v1` |

## TTL Matrix

| Namespace | TTL | Jitter |
|---|---|---|
| `business.details` | 60 min | ±15% |
| `recommendation.by_business` | 15 min | ±15% |
| `business.cities` | 12 hours | ±15% |

Jitter is applied at write time to prevent thundering-herd expiry storms.

## Stampede Protection

When a key expires under concurrent load, only one thread fetches from the DB.
Others wait on a `SET NX PX` distributed lock (5-second lease) rather than all firing
concurrent DB queries simultaneously.

## Fallback Rules

- Redis unavailable or timeout → request continues against DB/gRPC (fail-open, zero 5xx).
- Redis is never the source of truth.
- Invalidation happens after successful ingest commits, not before.

## Rollout Controls

| Variable | Effect |
|---|---|
| `CACHE_ROLLOUT_PERCENT` (0–100) | Route only N% of entity IDs through cache. Uses `md5(id) % 100` for deterministic bucket assignment. |
| `CACHE_SHADOW_MODE=true` | Always serve from DB; read Redis in background and log match/mismatch. Never serves stale data. |

Recommended rollout sequence: shadow mode → 5% → 25% → 50% → 100%.

## Observability

Structured log events:

| Event | Meaning |
|---|---|
| `cache_hit` | Served from Redis |
| `cache_miss` | Redis miss, fell through to DB/gRPC |
| `cache_set` | Populated Redis after DB fetch |
| `cache_get_failed` | Redis error on read (fail-open triggered) |
| `cache_set_failed` | Redis error on write (data still returned) |
| `cache_shadow` | Shadow mode match/mismatch result |
| `cache_invalidation` | Pattern deleted after ingest write |

Live stats endpoint (per service):

```
GET http://localhost:8001/cache/stats   # business-service
GET http://localhost:8002/cache/stats   # recommendation-service
GET http://localhost:8003/cache/stats   # ingestion-service invalidation stats
```

Important fields in the response:

- `hits`, `misses`, `errors`, `hit_rate`
- `cache_latency_ms_avg`, `cache_latency_ms_total`, `latency_samples`
- `invalidations`, `invalidated_keys`

On ingestion-service, `/cache/stats` focuses on invalidation activity triggered after ingest writes.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_ENABLED` | `true` | Set to `false` to bypass cache entirely |
| `REDIS_URL` | `redis://:password@redis:6379/0` | Connection string including auth |
| `REDIS_PASSWORD` | `dev_redis_pass` | Auth password; override in production |
| `REDIS_TIMEOUT_SECONDS` | `0.2` | Per-operation timeout; triggers fail-open |
| `CACHE_ROLLOUT_PERCENT` | `100` | 0 = off, 100 = full |
| `CACHE_SHADOW_MODE` | `false` | Validation mode without serving cache |

## Capacity Reference

| Namespace | Avg payload | Max keys | Est. memory |
|---|---|---|---|
| `business.details` | ~2 KB | 150,346 | ~300 MB worst-case |
| `recommendation.by_business` | ~4 KB | 150,346 × limit | ~600 MB worst-case |
| `business.cities` | ~1 KB | 1 | negligible |

Configured limit: 256 MB with `allkeys-lru` eviction. Working set in practice is much smaller.

## Performance Baseline

Measurement date: 2026-05-02

| KPI | Pre-cache (from runtime logs) | Post-cache (steady state) |
|---|---|---|
| Business search p50 latency | 0.22 ms | 0.22 ms (search layer unaffected) |
| Business search p95 latency | 0.32 ms | 0.32 ms (search layer unaffected) |
| Cache hit-rate | N/A | > 80% after warm-up |
| Repeat-request p95 (detail endpoint) | ~DB round-trip | < 5 ms (Redis) |

Notes:
- Search latency figures are for the PostgreSQL FTS/trigram path, not the cache layer.
- Cache hit-rate measured via `/cache/stats` after steady-state traffic.

## Load Testing

```bash
# Concurrent load test — reports p50/p95/p99 and cache hit-rate delta
python scripts/cache_load_test.py load --rounds 5 --concurrency 20

# Point-in-time stats snapshot
python scripts/cache_load_test.py stats
```

See `scripts/cache_load_test.py` for chaos test checklist (Redis kill & recovery).
