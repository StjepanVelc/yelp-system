# Redis Caching — Technical Summary

*Yelp-System · Production-grade cache layer on a real dataset (150K+ businesses)*

---

## Problem

A microservices Yelp clone queried PostgreSQL on every request.  
With 150K businesses, 7M reviews, and two services (business + recommendation), repeated
identical queries under concurrent load produced unnecessary DB round-trips and
unpredictable p95 latencies.

**Goal:** cut repeat-request latency by ≥60%, stay fully operational when Redis is down,
and prove correctness with a reproducible test suite.

---

## Architecture & Design Decisions

### Cache-aside pattern (not write-through)
Chosen because the business dataset is read-heavy and changes via a separate ingestion
pipeline. Write-through would couple two services unnecessarily.

### Namespaced keys with TTL + jitter
```
business.details:{id}      TTL 60 min  ± 10% jitter
recommendation.by_business:{id}   TTL 30 min  ± 10% jitter
business.cities            TTL 10 min  ± 10% jitter
```
Jitter prevents thundering-herd expiry storms where thousands of keys expire at the same
clock tick.

### Stampede protection (distributed lock)
When a key expires under load, only one thread fetches from the DB.  
Others wait on a Redis `SET NX PX` lock (5-second lease) rather than all firing
concurrent DB queries — the classic thundering-herd solution.

### Fail-open
Redis connectivity is checked at startup. If Redis is unreachable (or times out within
0.2 s), the services continue serving from PostgreSQL.  
`REDIS_ENABLED=false` disables the cache layer entirely without a code change.

### Per-entity rollout
`CACHE_ROLLOUT_PERCENT` uses `md5(entity_id) % 100` to deterministically route a
percentage of IDs through the cache. Allows canary deployment (5 % → 25 % → 100 %)
without any code change or service split.

### Shadow mode
`CACHE_SHADOW_MODE=true` makes services *always* read from DB but simultaneously reads
from Redis and logs whether they matched.  
Used for 24h validation before serving cached data to real traffic.

---

## Infrastructure

### Redis configuration (docker-compose)
| Parameter | Value | Rationale |
|---|---|---|
| `maxmemory` | 256 MB | Fits working set; ~300 MB worst-case for all business keys, but LRU keeps hot subset |
| `maxmemory-policy` | `allkeys-lru` | No explicit persistence requirement; hot keys survive, cold keys evict automatically |
| `appendonly yes` | AOF | Every write journalled; crash-safe recovery |
| `save 3600 1` / `300 100` / `60 10000` | RDB snapshots | Point-in-time backup for data import warm-starts |
| `requirepass` | env-var (`REDIS_PASSWORD`) | Auth baseline for all environments |
| Named volume `redis_data` | Docker volume | AOF/RDB persist across container restarts |

### Security baseline
- `requirepass` enforced on the Redis server; password injected via env var (not hardcoded).
- `REDIS_URL` includes password: `redis://:${REDIS_PASSWORD}@redis:6379/0`.
- In production: rotate `REDIS_PASSWORD`, use TLS tunnel or managed Redis (e.g. ElastiCache with in-transit encryption).
- ACL next step: separate read-only ACL for cache consumers vs. admin ACL for ingestion service.

---

## Observability

Two live dashboards (one per service):

```
GET /cache/stats   →  per-namespace hit/miss/error/lock/stampede counters
```

Thread-safe `CacheStats` class uses `collections.Counter` with locks.
`snapshot()` unions all five counter dicts to catch namespaces that only appear in
stampede or lock metrics.

---

## Metrics & KPIs

| Metric | Target | Instrument |
|---|---|---|
| Cache hit-rate | > 80% after warm-up | `/cache/stats` `hit_rate` |
| p95 response time (repeat request) | < 30 ms | service logs |
| DB QPS reduction | ≥ 60% under steady traffic | compare DB connection count before/after |
| Error-rate during Redis outage | 0% (fail-open) | service logs + HTTP status codes |
| Stampede lock contention | < 5% of misses | `stampede_waits` counter |

---

## Testing

**38 unit tests** (business-service) / **18 unit tests** (recommendation-service) covering:

| Test class | What it verifies |
|---|---|
| `TestCacheStats` | Counter accuracy, thread-safety, `snapshot()` completeness |
| `TestCacheLock` | Acquire/release, lock-held miss path |
| `TestCacheRollout` | Deterministic bucket assignment, 0% and 100% edge cases |
| `TestCacheStatsEndpoint` | HTTP `/cache/stats` returns correct shape |
| `TestRecommendationRollout` | Same rollout logic in recommendation-service |
| `TestRecommendationCacheStatsEndpoint` | Stats endpoint on port 8002 |

All tests run with `REDIS_ENABLED=false` — no running Redis required, no flaky I/O.

---

## Hardening & Chaos

`scripts/cache_load_test.py` provides:

```
load    # N concurrent requests, measures p50/p95/p99 + cache hit-rate delta
chaos   # Checklist: kill Redis mid-traffic, observe fail-open, verify auto-recovery
stats   # Point-in-time snapshot from both services
```

**Chaos outcome (verified manually):**
- 0 × 5xx during Redis downtime (fail-open active)
- Cache auto-recovers on Redis restart, no service restart needed
- `allkeys-lru` evicts cold keys; hot-key hit-rate recovers within one warm-up cycle

---

## Tradeoffs & What I'd Do Differently in Production

| Decision | Tradeoff |
|---|---|
| Cache-aside vs. write-through | Write-through would give stronger consistency; chosen cache-aside for simplicity and because ingest is a separate service |
| In-process Redis client vs. connection pool | `redis-py` uses its own connection pool; a production system would use `aioredis` throughout for native async |
| 256 MB single Redis node | Fine for a dev/staging dataset; production would use Redis Cluster or a managed service with read replicas |
| Jitter-based stampede mitigation | Works well; alternative is probabilistic early expiration (XFetch algorithm) for extremely hot keys |
| Password-only auth | Full ACL (read-only for consumers, write for ingestion) would be the next security step |

---

---

*All code is in `services/business-service`, `services/recommendation-service`, `services/ingestion-service`, and `services/frontend`.*  
*Infrastructure config: `docker-compose.yml`, `.env.example`.*  
*Runbook: `docs/redis-runbook.md`*
