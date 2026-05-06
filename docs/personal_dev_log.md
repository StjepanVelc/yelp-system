# Recent Updates Overview

Ovo je centralni pregled svega što je nedavno dodano/izmijenjeno, da ne moram pamtiti.

## 1) Live promet dashboard (browser aplikacija)

File: `scripts/traffic_dashboard.py`

Šta radi:
- pokreće mini web dashboard na `http://localhost:9999`
- generiše promet prema API endpointu koji zadaš
- prikazuje live KPI i grafikone (RPS, latencija, OK vs error)
- ima export dugmad:
  - Save RPS chart (PNG)
  - Save Latency chart (PNG)
  - Save OK/Err chart (PNG)
  - Save Full Report (HTML snapshot)

JWT podrška:
- `--gen-token` automatski kreira dev JWT (HS256)
- `--token <JWT>` koristi ručno zadan token
- `--jwt-secret <secret>` za slučaj da secret nije default

Sigurnosni uslov za load-test bypass:
- API gateway bypass radi samo kada su sva 3 uslova ispunjena:
  - `APP_ENV=development`
  - `ENABLE_DEV_LOAD_TEST_BYPASS=true`
  - token sadrži claim `dev_load_test=true`
- U svim ostalim slučajevima vrijedi normalna auth provjera.

Primjeri:

```powershell
python scripts/traffic_dashboard.py --gen-token
python scripts/traffic_dashboard.py --gen-token --url http://localhost:8000/api/businesses?searchQuery=&city=Arizona&minStars=&searchPath=auto --workers 24 --duration 180
python scripts/traffic_dashboard.py --url http://localhost:8000/health --workers 8 --duration 60
```

## 2) Live monitor skripta + HTML report

File: `scripts/traffic_live_monitor.py`

Što radi:
- šalje promet i printa live metrike u terminal
- zapisuje artefakte u `test-results/traffic-monitor-.../`
- generiše statički HTML report sa grafovima

Companion docs:
- `docs/testing-traffic-live.md`

## 3) LAN test vodič (2 laptopa)

File:
- `docs/testing-lan.md`

Sadrži:
- host/client korake
- LAN URL provjere
- map check
- firewall command
- troubleshooting sekciju

## 4) Frontend LAN origin fix (Next dev)

File:
- `services/frontend/next.config.js`

Što je dodano:
- `allowedDevOrigins` više nije hardcoded na jednu IP
- automatski skuplja sve lokalne IPv4 adrese
- podržava dodatne hostove preko `NEXT_ALLOWED_DEV_ORIGINS`

## 5) Gateway user status fail-open u developmentu

File:
- `services/api-gateway/app/clients/user_status_client.py`

Što je promijenjeno:
- ako user status servis (`:8004`) nije dostupan i `APP_ENV=development`, gateway više ne ruši request nego tretira usera kao aktivnog
- za non-development okruženja ponašanje ostaje strogo (error se i dalje diže)

## 6) Dodatni test alat koji već postoji

File:
- `scripts/test-all.ps1`

Služi za širi test flow i output fajlove (`summary.txt`, `summary.json`, step logovi).

---

## Quick Start (što najčešće treba)

1. Pokreni lokalni stack:

```powershell
powershell -ExecutionPolicy Bypass -File local-dev.ps1 -Action start
```

2. Pokreni live dashboard s auth tokenom:

```powershell
$env:ENABLE_DEV_LOAD_TEST_BYPASS = "true"
python scripts/traffic_dashboard.py --gen-token
```

3. Otvori `http://localhost:9999` i testiraj export dugmad.

4. Nakon load testa vrati bypass na sigurno stanje:

```powershell
$env:ENABLE_DEV_LOAD_TEST_BYPASS = "false"
```

---

## 7) Load Testing Framework (Najnovije)

Opis:
- integrirani test alati za testiranje svakog servisa i endpointa
- praćenje ključnih metrika pod opterećenjem

Praćene metrike:
- **Success rate** — % uspješnih zahtjeva
- **Errors** — broj i tipovi grešaka
- **Average RPS** — prosječnih zahtjeva po sekundi
- **P95 latency** — 95. percentila latencije
- **Service-by-service endpoint behavior** — kako se svaki endpoint ponaša

Alati koji se koriste:
- `scripts/traffic_dashboard.py` — interaktivni live dashboard
- `scripts/traffic_live_monitor.py` — terminal monitor s HTML reportom
- `scripts/traffic_load_test.py` — automatizirana opterećenja testiranja

---

## 8) Engineering Focus

Projekt je fokusiran na razumijevanje:

1. **Kako backend servisi međusobno komuniciraju**
   - gRPC između servisa
   - API Gateway routing i validacija

2. **Kako promet teče kroz API Gateway**
   - request lifecycle (end-to-end)
   - fail-open i resilience pattern

3. **Kako se data-heavy sistemi ponašaju pod opterećenjem**
   - load testing i traffic simulation
   - monitoring performance degradacije

4. **Kako caching, indexing i boundaries utječu na performansu**
   - Redis cache-aside implementacija s TTL jitter i stampede protection
   - Database indexing strategija
   - Service isolation i data consistency

---

## 9) Redis Caching (Production-Grade)

Trenutno stanje:
- `GET /businesses/{id}` → `business.details` (TTL 60 min)
- `GET /businesses/cities` → `business.cities` (TTL 12 h)
- `GET /recommendations/{id}` → `recommendation.by_business` (TTL 15 min)

Implementirane capabilities:
- ✅ TTL jitter (±15%) — sprječava synchronized expiry spikes
- ✅ Stampede protection — distributed lock (`SET NX PX`)
- ✅ Fail-open behavior — servisi nastave preko DB/gRPC ako Redis pada
- ✅ Canary rollout — `CACHE_ROLLOUT_PERCENT`, `CACHE_SHADOW_MODE`
- ✅ Invalidation — nakon ingestion writes
- ✅ Redis hardening — `allkeys-lru`, 256 MB cap, `requirepass`, AOF + RDB
- ✅ Per-service stats — `/cache/stats` endpoint

Dokumentacija:
- `docs/redis-cache.md` — cache contract, key format, TTL matrix, rollout flags
- `docs/redis-runbook.md` — operations, alerting, incidents, backup/restore

---

## 10) Future Roadmap

Planirano:
- 🔄 Redis Cluster ili managed Redis failover
- 🔄 Event-driven CDC invalidation (Debezium)
- 🔄 CI/CD pipeline (GitHub Actions)
- 🔄 Enhanced monitoring i alerting
- 🔄 Chaos engineering testovi

---

## Sadržaj dokumentacije (Pregled)

| File | Namjena |
| --- | --- |
| `docs/redis-cache.md` | Cache contract, key format, TTL, rollout |
| `docs/redis-runbook.md` | Operations, alerting, troubleshooting |
| `docs/search-observability.md` | Search path control, fallback, metrics |
| `docs/jwt-authentication.md` | Bearer token validation, claims, roles |
| `docs/testing-traffic-live.md` | Live traffic testing vodič |
| `docs/testing-lan.md` | 2-laptop LAN setup vodič |
| `docs/engineering-notes.md` | Dodatne implementacijske napomene |
| `docs/environment-variables.md` | Konfiguracija i env varijable |
