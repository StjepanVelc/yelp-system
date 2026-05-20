# Latency Investigation Plan

**Datum**: 2026-05-20  
**Scope**: API odazivi kroz Gateway + direktni servisi  
**Status**: In progress

## 1. Trenutno stanje (izmjereno)

### Health
- `http://localhost:8000/health` -> 200
- `http://localhost:8001/health` -> 200
- `http://localhost:8002/health` -> 200
- `http://localhost:8003/health` -> 200

### Gateway latencije (10 uzoraka, auth token)
- `GET /businesses/{id}`: p50 ~3241 ms, p95 ~3296 ms, avg ~3232 ms
- `GET /businesses/cities`: p50 ~3261 ms, p95 ~3338 ms, avg ~3268 ms
- `GET /recommendations/{id}?limit=5`: p50 ~3394 ms, p95 ~3473 ms, avg ~3391 ms

### Direktni servisi (10 uzoraka)
- `business-service /businesses/{id}`: p50 ~2038 ms, p95 ~2049 ms
- `business-service /businesses/cities`: p50 ~2082 ms, p95 ~2197 ms
- `recommendation-service /recommendations/{id}?limit=5`: p50 ~2154 ms, p95 ~2199 ms
- `business-service /users/{id}/status`: p50 ~2042 ms, p95 ~2063 ms

## 2. Kratki zaključak

- Glavni problem nije samo Gateway. I direktni servisi su oko 2.0-2.2s.
- Gateway dodaje dodatni sloj latencije (auth + user-status check + proxy), pa ukupno završi na ~3.2-3.5s.
- Trenutni odazivi su previsoki za normalan API UX.

## 3. Hipoteze uskog grla

1. User-status provjera u Gateway-u dodaje velik fixed overhead po requestu.
2. Upstream pozivi u Gateway klijentima otvaraju novi `httpx.AsyncClient` po requestu (nema pooling reuse).
3. Business/recommendation servisi imaju spor DB put (upit, indeks, ili čekanje na external dependency).
4. Cache hit-rate možda nije dovoljno visok za promet koji testiramo.

## 4. Plan optimizacije (redoslijed)

## Faza A - Brzi dobitak (Gateway)

1. Uvesti shared `httpx.AsyncClient` u API Gateway-u (lifespan singleton, connection pooling).
2. Uvesti kratki in-memory cache za user-status u Gateway-u (npr. TTL 30-60s po `user_id`).
3. Spustiti i kontrolirati `USER_STATUS_TIMEOUT_SECONDS` u dev/profili testa (npr. 0.5-1.0s) uz fail-open/fail-fast odluku po okruženju.

**Cilj nakon Faze A**:
- Skinuti ~500-1200ms sa gateway puta.

## Faza B - Servisni bottleneck (Business/Recommendation)

1. Izmjeriti SQL trajanja po endpointu (`/businesses/{id}`, `/businesses/cities`, `/recommendations/{id}`).
2. Provjeriti indekse i execution plan za najsporije upite.
3. Provjeriti cache hit-rate preko `/cache/stats` tijekom benchmarka.
4. Provjeriti vrijeme prema Redis-u i broj miss-eva na toplom cacheu.

**Cilj nakon Faze B**:
- Direktni servisi spustiti s ~2.1s prema <800ms.

## Faza C - Stabilizacija i regresijski guard

1. Napraviti benchmark skriptu sa:
   - warmup + measured fazom
   - auth token inputom (`BENCHMARK_BEARER_TOKEN`)
   - p50/p95/p99 + status histogram
2. Definirati pragove:
   - soft gate: p95 < 1000ms
   - hard gate: p95 < 500ms
3. Spremati rezultate u `test-results/` za prije/poslije usporedbu.

## 5. Konkretni zadaci za istraživanje (checklist)

- [ ] Izmjeriti user-status call zasebno iz Gateway-a pod loadom.
- [ ] Provjeriti koliko traje auth+user-status dio u middleware/dependency layeru.
- [ ] Provjeriti SQL execution plan za business details i recommendations.
- [ ] Provjeriti cache hit-rate prije i poslije warmup-a.
- [ ] Potvrditi da reuse HTTP klijenta radi i pod concurrencyjem.

## 6. Očekivani target odazivi

- `GET /businesses/{id}`: p95 < 500ms
- `GET /businesses/cities`: p95 < 300ms
- `GET /recommendations/{id}?limit=5`: p95 < 700ms

Napomena: targeti su realni tek nakon optimizacije i toplog cache scenarija.

## 7. Što ne raditi odmah

- Ne uvoditi velike arhitekturne promjene prije mjerenja (npr. CDC refactor ili novi storage).
- Ne “gađati” random timeout vrijednosti bez baseline trace/metrika.
- Ne miješati Phase 3 scope dok se Phase 2 performance baseline ne stabilizira.
