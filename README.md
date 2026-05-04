![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Docker](https://img.shields.io/badge/Docker-enabled-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)

# ⭐ Yelp System — Microservices Architecture

Distributed microservices application for **business search and recommendations**, powered by the Yelp Open Dataset (~10M+ records).

---

## 🚀 Overview

This project demonstrates a **production-style microservices architecture** with:

* FastAPI-based backend services
* PostgreSQL database (~10M+ records)
* gRPC communication between services
* API Gateway pattern
* Nginx reverse proxy (rate limiting + security headers)
* SSR frontend (Next.js)

---

## 🖥️ Application Preview

### 🔍 Search Page

![Search Page](docs/image/search-page.png)

### 📄 Business Detail

![Business Detail](docs/image/business-detail.png)

### ⭐ Recommendations Engine

![Recommendations](docs/image/recommendations.png)

### 📝 Reviews System

![Reviews](docs/image/reviews.png)

---

## 🧠 System Architecture

![Architecture](docs/image/Architecture.png)

---

## 🗄️ Database Schema

![Database](docs/image/database.png)

* ~10.2 million records
* 5 main tables: `businesses`, `users`, `reviews`, `tips`, `checkins`
* Indexed for performance (city, stars, review_count…)

---

## ⚙️ Architecture Breakdown

```
Browser
  │
  ▼
Nginx (:80)
  ├── /api/*  → API Gateway (:8000)
  │               ├── Business Service (:8001)
  │               └── Recommendation Service (:8002)
  │
  └── Frontend (Next.js :3000)

Business Service
  ├── REST API
  ├── gRPC Server (:50051)
  └── PostgreSQL

Recommendation Service
  ├── REST API
  └── gRPC Client → Business Service

Ingestion Service
  └── Loads Yelp dataset into PostgreSQL
```

---

## 🔍 Core Features

* ✅ Business search (city + rating filters)
* ✅ Full-text search with runtime path control (`search_path=auto|fts|trigram|legacy`)
* ✅ Business detail page (categories, location, status)
* ✅ Recommendation engine (distance + category + rating)
* ✅ Reviews system (paginated, sorted)
* ✅ Interactive map on business detail (Leaflet + OpenStreetMap)
* ✅ Redis cache layer (cache-aside, stampede protection, rollout flags, observability)
* ✅ gRPC communication between services
* ✅ API Gateway routing & validation
* ✅ Rate limiting + security headers (Nginx)
* ✅ Dockerized infrastructure

---

## 🧮 Recommendation Logic

Recommendations are calculated based on:

* 📍 Geographic proximity (Haversine distance)
* 🏷️ Category overlap
* ⭐ Rating similarity
* 🔥 Popularity (review count)
* 🟢 Business status (open/closed)

Custom scoring function ranks candidates and returns the most relevant results.

---

## 📊 Data

| Table      | Records    |
| ---------- | ---------- |
| businesses | 150,346    |
| users      | 1,987,897  |
| reviews    | 6,990,280  |
| tips       | 908,915    |
| checkins   | 131,930    |
| **Total**  | **~10.2M** |

---

## 🧪 Running the Project

## 🔐 Environment Variables (Professional Setup)

Use a 3-layer env strategy:

* Root [./.env.example](.env.example): committed template with safe placeholder values
* Root .env: local private file (never commit)
* Production: CI/CD or secret manager variables (never from repository files)

### Local setup

1. Copy template:

```bash
cp .env.example .env
```

2. Update local secrets in .env (at minimum DB password and JWT secret).

3. For test profile, copy [./.env.test.example](.env.test.example) to `.env.test` and adjust credentials.

### Git safety

[./.gitignore](.gitignore) is configured to ignore env files while keeping the template:

* `.env`
* `.env.*`
* `!.env.example`

### Docker behavior

[docker-compose.yml](docker-compose.yml) reads from root .env via `env_file` and supports defaults via `${VAR:-default}`.
For production deployments, inject values from CI/CD instead of shipping .env files in repo.

### Startup validation

Critical settings are now validated during service startup:

* `DATABASE_URL` is required for business-service, recommendation-service, ingestion-service
* `JWT_SECRET` is required for api-gateway
* In `production`/`staging`, placeholder values (like `change_me` or default dev JWT secret) are rejected

This catches misconfiguration early and reduces "works on my machine" issues.

---

### ▶️ Local Development

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Business Service
cd services/business-service
uvicorn app.main:app --port 8001 --reload

# Recommendation Service
cd services/recommendation-service
uvicorn app.main:app --port 8002 --reload

# API Gateway
cd services/api-gateway
uvicorn app.main:app --port 8000 --reload

# Frontend
cd services/frontend
npm run dev
```

Frontend runs at:
http://localhost:3000

---

### 🐳 Docker Setup

```bash
docker compose up --build
```

After large backend/frontend/config changes, rebuild images before starting containers:

```bash
docker compose build --no-cache
docker compose up -d
```

After startup:

| URL                             | Service           |
| ------------------------------- | ----------------- |
| http://localhost                | Nginx → Frontend  |
| http://localhost/api/businesses | API               |
| http://localhost:3000           | Frontend (direct) |

---

## 🧰 Tech Stack

| Layer      | Technology                          |
| ---------- | ----------------------------------- |
| Frontend   | Next.js, React, TypeScript, Leaflet |
| Backend    | FastAPI, Python                     |
| Cache      | Redis 7 (cache-aside, LRU)          |
| Database   | PostgreSQL                          |
| ORM        | SQLAlchemy                          |
| RPC        | gRPC                                |
| Proxy      | Nginx                               |
| Containers | Docker                              |

---

## 🛠️ Future Improvements

* Redis Cluster / managed failover (ElastiCache)
* Event-driven cache invalidation (CDC via Debezium)
* CI/CD pipeline (GitHub Actions)

---

## ⚡ Redis Caching

Production-grade cache-aside layer built on Redis 7, covering all high-traffic read routes.

### What's cached

| Endpoint | Namespace | TTL |
|---|---|---|
| `GET /businesses/{id}` | `business.details` | 60 min |
| `GET /businesses/cities` | `business.cities` | 12 h |
| `GET /recommendations/{id}` | `recommendation.by_business` | 15 min |

All TTLs include ±15% random jitter to spread expiry across time and avoid thundering-herd storms.

### Key design decisions

**Stampede protection** — when a hot key expires, a single `SET NX PX` distributed lock gates the DB fetch. Concurrent requests wait (up to 5 s) rather than all firing parallel queries.

**Fail-open** — Redis is optional. If unreachable or slow (> 0.2 s timeout), every service falls through to PostgreSQL/gRPC and returns 200. Zero downtime from a Redis outage.

**Canary rollout** — `CACHE_ROLLOUT_PERCENT` (0–100) uses `md5(entity_id) % 100` to deterministically route a fraction of IDs through the cache. Allows gradual exposure without code changes.

**Shadow mode** — `CACHE_SHADOW_MODE=true` always serves from DB, reads Redis in parallel, and logs whether the values matched. Used for pre-launch validation.

**Write-through invalidation** — the ingestion service deletes affected cache keys after successful DB writes so stale data never outlives an ingest run.

### Infrastructure

| Config | Value | Why |
|---|---|---|
| `maxmemory` | 256 MB | Covers hot working set; LRU evicts cold keys automatically |
| `maxmemory-policy` | `allkeys-lru` | Evict least-recently-used across all keys |
| AOF (`appendonly yes`) | enabled | Crash-safe write journal |
| RDB snapshots | 60 s / 300 s / 3600 s | Point-in-time backup for warm restarts |
| Auth | `requirepass` via `REDIS_PASSWORD` env var | No hardcoded credentials |
| Persistence volume | `redis_data` Docker volume | Survives container restarts |

### Observability

Each service exposes a live stats endpoint:

```
GET http://localhost:8001/cache/stats   # business-service
GET http://localhost:8002/cache/stats   # recommendation-service
```

Response includes per-namespace `hits`, `misses`, `errors`, `hit_rate`, `locks_acquired`, `stampede_waits`.

### Load & chaos testing

```bash
# Concurrent load test — reports p50/p95/p99 + hit-rate delta
python scripts/cache_load_test.py load --rounds 5 --concurrency 20

# Kill Redis mid-traffic and verify fail-open (checklist)
python scripts/cache_load_test.py chaos
```

Docs:

* [docs/redis-cache.md](docs/redis-cache.md) — key contract, TTL matrix, environment variables
* [docs/redis-runbook.md](docs/redis-runbook.md) — alert thresholds, rollout sequence, incident procedures, backup/restore

---

## 📡 API Endpoints

All external requests go through the **API Gateway** (`:8000`).

---

## 🔎 Search Rollout & Observability

Business search supports controlled rollout and diagnostics through a single semantic model.

### Request query params

* `query`: free-text search phrase (max 200 chars)
* `search_path`: `auto | fts | trigram | legacy`

Behavior:

* `auto` (default): FTS first, then trigram fallback for low/zero-result scenarios
* `fts`: force FTS only (diagnostics)
* `trigram`: force trigram only (diagnostics)
* `legacy`: force legacy SQL filter path (safe rollback)

### Response headers

* `X-Search-Path`: `fts | trigram | legacy`
* `X-Search-Version`: `v2 | legacy`
* `X-Search-Latency-Ms`: integer latency in milliseconds

### Logged search metrics

Each `/businesses` request emits a structured `search_metrics` log line with:

* `path`
* `version`
* `latency_ms`
* `result_count`
* `zero_results`
* `query_hash` (first 12 chars of SHA-256, never raw query)
* `fallback_reason` (`forced_legacy`, `forced_trigram`, `fts_low_results`, `fts_zero_results`, `fts_timeout`, `fts_error`, `no_query`)

### Fail-safe behavior

If FTS fails or times out, business-service automatically falls back to `legacy` and logs the reason.

### Example

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  "http://localhost:8000/businesses?query=pizza+tucson&search_path=auto&city=Phoenix"
```

---

## 🧪 Frontend Dev Search Debug

Frontend has a dev-mode debug panel that shows search execution metadata (`X-Search-*`).

Enabled by default in non-production builds.
You can also force-enable it with:

`NEXT_PUBLIC_SHOW_SEARCH_DEBUG=1`

When enabled:

* Search form exposes a `Path` selector (`auto|fts|trigram|legacy`)
* Results page shows path, version and latency reported by API Gateway

---

## 🔐 JWT Authentication (API Gateway)

All protected routes validate:

* Authorization header format (`Bearer <token>`)
* JWT signature + claims (`iss`, `aud`, `exp`, `sub`)
* Route-level required role
* Runtime user status (`active/deleted`) through user-status service

### Response model

* `401`:

  * no token
  * malformed authorization header
  * invalid token
  * expired token
* `403`:

  * missing role
  * insufficient role
  * inactive/deleted user

### Expected JWT claims

```json
{
  "sub": "user-123",
  "iss": "yelp-auth",
  "aud": "yelp-api",
  "roles": ["business:read", "recommendation:read"],
  "iat": 1714370000,
  "exp": 1714373600
}
```

### Authorization header example

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  "http://localhost:8000/businesses?city=Phoenix"
```

### Gateway JWT config (env)

`JWT_SECRET`, `JWT_ALGORITHM`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_LEEWAY_SECONDS`, `JWT_ROLES_CLAIM`

Role mapping:

`BUSINESS_REQUIRED_ROLES`, `RECOMMENDATION_REQUIRED_ROLES`

User status runtime check:

`USER_SERVICE_URL`, `USER_STATUS_PATH_TEMPLATE`, `USER_STATUS_TIMEOUT_SECONDS`

Frontend sends `Authorization` automatically if token is available in:

* `NEXT_PUBLIC_API_AUTH_TOKEN` / `API_AUTH_TOKEN` env
* `localStorage["api_auth_token"]`

---

### 🏢 Business Endpoints

| Method | Endpoint                   | Description                                                      |
| ------ | -------------------------- | ---------------------------------------------------------------- |
| `GET`  | `/businesses`              | Search businesses (`?city=`, `?query=`, `?search_path=`, `?min_stars=`, `?page=`, `?limit=`) |
| `GET`  | `/businesses/{id}`         | Get business details by ID                                       |
| `GET`  | `/businesses/{id}/reviews` | Get paginated reviews (`?page=`, `?limit=`)                      |

---

### ⭐ Recommendation Endpoints

| Method | Endpoint                | Description                        |
| ------ | ----------------------- | ---------------------------------- |
| `GET`  | `/recommendations/{id}` | Get similar businesses (`?limit=`) |

---

### ❤️ Health Check

| Method | Endpoint  | Description               |
| ------ | --------- | ------------------------- |
| `GET`  | `/health` | API Gateway health status |

---

## 📌 Notes

* Built as a **production-style system design project**
* Focus on:

  * scalability
  * service isolation
  * clean architecture
* Dataset: **Yelp Open Dataset (~10M+ records)**

Additional implementation and debugging notes are available in docs/engineering-notes.md.
---

## 👤 Author

**Stjepan Velc**

Backend & System Design focused developer

**Tech stack:**
Python • FastAPI • Microservices • PostgreSQL

