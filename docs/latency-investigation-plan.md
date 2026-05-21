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

- [x] Izmjeriti user-status call zasebno iz Gateway-a pod loadom. Učinjeno: prvi poziv ~649 ms, cache hitovi ~0.3-0.4 ms.
- [x] Provjeriti koliko traje auth+user-status dio u middleware/dependency layeru. Učinjeno: auth ukupno ~623 ms, parse/decode zanemarivo, user-status dio nosi gotovo sav trošak.
- [x] Provjeriti SQL execution plan za business details i recommendations. Business details je provjeren; recommendations path je gRPC + ranking, pa SQL execution plan tu nije primjenjiv. Za recommendation backend je provjeren stvarni gRPC put i povratni rezultat.
- [x] Provjeriti cache hit-rate prije i poslije warmup-a. Učinjeno: initial miss, zatim cache hitovi na istom user_id.
- [x] Potvrditi da reuse HTTP klijenta radi i pod concurrencyjem. Učinjeno: 10 paralelnih zahtjeva prošlo bez grešaka.

## 6. Očekivani target odazivi

- `GET /businesses/{id}`: p95 < 500ms
- `GET /businesses/cities`: p95 < 300ms
- `GET /recommendations/{id}?limit=5`: p95 < 700ms

Napomena: targeti su realni tek nakon optimizacije i toplog cache scenarija.

## 7. Što ne raditi odmah

- Ne uvoditi velike arhitekturne promjene prije mjerenja (npr. CDC refactor ili novi storage).
- Ne “gađati” random timeout vrijednosti bez baseline trace/metrika.
- Ne miješati Phase 3 scope dok se Phase 2 performance baseline ne stabilizira.

## 8. Riješen odaziv (prije / poslije)

### Root cause

- Na Windows lokalnom setupu `localhost` je išao kroz IPv6/IPv4 fallback i dodavao oko 2 sekunde po requestu.
- Direktan test je pokazao da `localhost` daje oko 2000 ms, dok `127.0.0.1` daje oko 10-20 ms.
- Zato je `local-dev.ps1` prebačen na `127.0.0.1` loopback adrese za lokalne servise.

### Što je sve bio problem

1. Lokalni hostname resolution na Windowsu je stvarao veliki fixed delay prije nego što je request uopće stigao do aplikacije.
2. Taj delay je zahvaćao i direktne pozive na servise i Gateway pozive, pa je izgledalo kao da je cijeli stack spor.
3. U prvim mjerenjima to je zamaglilo stvarni uzrok i otvorilo sumnju na auth, cache, DB i proxy sloj.
4. Tek kad je test uspoređen na `localhost` vs `127.0.0.1`, postalo je jasno da je problem u host resolutionu, a ne u poslovnoj logici servisa.
5. Zbog toga je lokalni benchmark morao biti ponovljen s loopback adresama da bi brojke bile smisleno usporedive.

### Što je odbačeno kao glavni uzrok

- DB upiti nisu objašnjavali puni trošak jer su i jednostavni endpointi kasnili približno jednako.
- Cache nije bio glavni problem jer su i cache-hit scenariji ostajali spori dok je korišten `localhost`.
- Gateway auth i user-status logika jesu trošak, ali nisu bili razlog za 2s baseline na direktnim servisima.

### Prije

- `GET /businesses/{id}` kroz Gateway: p50 ~3241 ms, p95 ~3296 ms, avg ~3232 ms
- `GET /businesses/cities` kroz Gateway: p50 ~3261 ms, p95 ~3338 ms, avg ~3268 ms
- `GET /recommendations/{id}?limit=5` kroz Gateway: p50 ~3394 ms, p95 ~3473 ms, avg ~3391 ms
- Direktni `business-service` endpointi: oko 2000 ms po requestu

### Poslije

- `http://127.0.0.1:8001/businesses/cities`: 15.37 ms
- `http://127.0.0.1:8001/businesses/Pns2l4eNsfO8kk83dixA6A`: 17.37 ms
- `http://127.0.0.1:8000/api/businesses/cities`: 12.53 ms
- `http://127.0.0.1:8000/api/businesses/Pns2l4eNsfO8kk83dixA6A`: 10.21 ms

### Zaključak

- Gateway i business-service su sad u target zoni za lokalni development.
- “2s problem” nije bio DB ni cache, nego hostname/network resolution na `localhost`.
- Za lokalno testiranje treba koristiti loopback `127.0.0.1`; za Docker/compose ostaju postojeće interne service adrese.

### Kratki rezime za prijenos u report

- Problem je bio kombinacija Windows `localhost` resolutiona i lokalnih testnih URL-ova koji su išli kroz spor fallback put.
- To je stvaralo umjetni fixed delay od oko 2 sekunde po requestu i činilo cijeli stack sporijim nego što stvarno jest.
- Nakon prebacivanja na `127.0.0.1`, i Gateway i direktni servisi pali su u desetke milisekundi.
