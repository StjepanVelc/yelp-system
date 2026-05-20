# Faza 2 - Cache Hardening Implementation Documentation

**Datum**: Maj 2026  
**Status**: ✅ Završeno  
**Autor**: Stjepan

## Sažetak

Faza 2 je učvrstila postojeći Redis cache-aside sloj bez promjene semantike aplikacije. Fokus je bio na mjerljivosti, fail-open ponašanju, TTL/jitter pravilima, invalidation observabilityju i jasnom cache contractu po namespaceu.

Ova faza nije uvodila CDC, write-through, write-back niti cache za search rezultate. PostgreSQL je i dalje source of truth, a Redis ostaje advisory cache sloj.

---

## 1. Arhitektura

### Cache tok po servisima

```text
Frontend / API Gateway
        |
        v
Business Service / Recommendation Service
        |
        |-- cache hit  -> Redis -> vrati odgovor
        |
        |-- cache miss -> DB / gRPC -> vrati odgovor -> upiši u Redis
        |
        '-- cache error/unreachable -> fail-open -> DB / gRPC

Ingestion Service
        |
        '-- nakon uspješnog write-a -> pattern invalidation u Redisu
```

### Aktivni cache namespace-i

- `business.details`
- `business.cities`
- `recommendation.by_business`

### Aktivni cache ključevi

- `yelp:{env}:business:details:{business_id}:v1`
- `yelp:{env}:business:cities:all:v1`
- `yelp:{env}:recommendation:by_business:{business_id}:{limit}:v1`

---

## 2. Implementirane komponente

### 2.1 Cache contract i key namespace dokumentacija

**Datoteke**:
- `docs/redis-cache.md`
- `docs/redis-runbook.md`

**Implementacija**:
- dokumentiran key format po namespaceu
- dokumentirane TTL vrijednosti i jitter pravila
- zapisano da Redis nije source of truth
- zapisano fail-open ponašanje i rollout controls
- dokumentirani stats endpointi i operativni response shape

**Vrijednost**:
- cache layer je sada objašnjen kao operativni dio sustava, ne samo kao interni kod
- postoji jedno mjesto za key schema, TTL i incident procedure

---

### 2.2 Read-side cache metrike i stats endpointi

**Datoteke**:
- `services/business-service/app/core/cache.py`
- `services/business-service/app/api/routes.py`
- `services/recommendation-service/app/core/cache.py`
- `services/recommendation-service/app/api/routes.py`

**Implementacija**:
- thread-safe in-memory stats po namespaceu
- praćenje:
  - `hits`
  - `misses`
  - `errors`
  - `hit_rate`
  - `locks_acquired`
  - `stampede_waits`
  - `latency_samples`
  - `cache_latency_ms_total`
  - `cache_latency_ms_avg`
  - `invalidations`
  - `invalidated_keys`
- stats dostupni preko:
  - `GET /cache/stats` na business-service
  - `GET /cache/stats` na recommendation-service

**Primjer odgovora**:

```json
{
  "namespaces": {
    "business.details": {
      "hits": 10,
      "misses": 2,
      "errors": 0,
      "hit_rate": 0.8333,
      "locks_acquired": 1,
      "stampede_waits": 0,
      "latency_samples": 12,
      "cache_latency_ms_total": 18.4,
      "cache_latency_ms_avg": 1.53,
      "invalidations": 0,
      "invalidated_keys": 0
    }
  },
  "total": {
    "hits": 10,
    "misses": 2,
    "errors": 0,
    "hit_rate": 0.8333,
    "latency_samples": 12,
    "cache_latency_ms_total": 18.4,
    "cache_latency_ms_avg": 1.53,
    "invalidations": 0,
    "invalidated_keys": 0
  }
}
```

**Vrijednost**:
- hit/miss/error više nije skriven samo u logovima
- cache latency je mjerljiv po namespaceu
- lock/stampede ponašanje je vidljivo tijekom opterećenja

---

### 2.3 TTL i jitter pravila

**Datoteke**:
- `services/business-service/app/core/cache.py`
- `services/recommendation-service/app/core/cache.py`
- `docs/redis-cache.md`

**Implementacija**:
- TTL jitter pri write-u da se izbjegne sinkroni expiry spike
- dokumentirana aktivna TTL matrica:
  - `business.details` -> 60 min
  - `recommendation.by_business` -> 15 min
  - `business.cities` -> 12 h
- jitter: `±15%`

**Vrijednost**:
- smanjen rizik thundering herd expiranja
- TTL ponašanje je jasno zapisano i stabilno

---

### 2.4 Stampede protection i fail-open ponašanje

**Datoteke**:
- `services/business-service/app/core/cache.py`
- `services/recommendation-service/app/core/cache.py`
- `docs/redis-runbook.md`

**Implementacija**:
- kratki distributed lock (`SET NX PX`) za hot-key expiry situacije
- `stampede_waits` i `locks_acquired` u stats responseu
- Redis error ili timeout ne ruši request path
- servis nastavlja preko DB/gRPC ako Redis nije dostupan

**Vrijednost**:
- cache layer ne uvodi hard dependency za availability
- under-load ponašanje je predvidljivije

---

### 2.5 Write-trigger invalidation observability

**Datoteke**:
- `services/ingestion-service/app/core/cache.py`
- `services/ingestion-service/app/service/ingestion_service.py`
- `services/ingestion-service/app/main.py`

**Implementacija**:
- ingestion-service pattern invalidation nakon uspješnog write-a
- invalidation stats po namespaceu:
  - `invalidations`
  - `invalidated_keys`
  - `errors`
- novi endpoint:
  - `GET /cache/stats` na ingestion-service

**Trenutni invalidation mapping**:
- `businesses` write:
  - `business.details`
  - `business.cities`
  - `recommendation.by_business`
- `reviews` write:
  - `recommendation.by_business`
- `users` write:
  - `recommendation.by_business`

**Vrijednost**:
- invalidation count se sada može direktno promatrati
- write-trigger ponašanje više nije dokazivo samo preko logova

---

## 3. Testiranje i verifikacija

### 3.1 Unit i endpoint testovi

**Datoteke**:
- `services/business-service/tests/test_business.py`
- `services/recommendation-service/tests/test_recommendation.py`
- `services/ingestion-service/tests/test_ingestion.py`

**Pokriveno**:
- `CacheStats` snapshot i hit-rate računanje
- latency i invalidation fields u stats responseu
- `GET /cache/stats` shape za business-service
- `GET /cache/stats` shape za recommendation-service
- `GET /cache/stats` shape za ingestion-service
- smoke test za `POST /ingest/businesses` -> rast invalidation counters
- smoke test za `POST /ingest/reviews` -> rast invalidation counters

**Validirano u ovom radu**:
- business cache testovi prolaze
- recommendation cache testovi prolaze
- ingestion invalidation/cache stats testovi prolaze

### 3.2 Rezultati test runa (2026-05-20)

#### Full service suite (informativno)

- `services/business-service/tests`: **28 passed, 11 errors**
  - glavni razlog: gRPC bind konflikt na portu `50051` u test okruženju (`Failed to bind to address [::]:50051`)
- `services/recommendation-service/tests`: **18 passed**
- `services/ingestion-service/tests`: **21 passed, 3 failed**
  - parser/loader mismatch testovi (`KeyError: 'id'`, `KeyError: 'business_id'`)

Napomena:
- Ovi full-suite problemi nisu blocker za phase 2 cache hardening scope.

#### Phase 2 ciljano testiranje

- Business cache unit klase (`TestCacheStats`, `TestCacheLock`, `TestCacheRollout`): **16 passed**
- Recommendation phase 2 subset (`RecommendationRollout`, `CacheStatsEndpoint`): **7 passed**
- Ingestion phase 2 subset (`InvalidationStats`, `/cache/stats`, smoke testovi za businesses/reviews ingest): **5 passed**

Zaključak ciljane validacije:
- sve ključne phase 2 promjene imaju zelen test signal.

---

## 4. Što je završeno iz MVP scopea

Prema planu iz Faze 2, završeno je:

- dokumentiran trenutni cache contract i key namespace
- mjeri se hit/miss/error
- mjeri se cache latency
- mjeri se invalidation count
- TTL i jitter su zadržani i dokumentirani
- fallback invalidation ostaje aktivan
- jasno je zapisano da Redis nije source of truth

Drugim riječima: **MVP scope Faze 2 je implementiran u kodu i dokumentaciji.**

---

## 5. Što nije dio ove faze

Namjerno nije rađeno u Fazi 2:

- cache za search rezultate
- write-through ili write-back model
- globalni refactor key schema
- CDC / Debezium / Kafka invalidation
- full replay ili backfill invalidation

To ostaje scope za Fazu 3 i dalje.

---

## 6. Zaključak

Faza 2 je tehnički implementirana i pokriva planirani MVP cache hardening scope. Cache layer sada ima:

- jasan contract
- TTL/jitter pravila
- read-side stats i latency metrike
- write-trigger invalidation observability
- smoke testove za glavne invalidation putove
- operativnu dokumentaciju i runbook

Faza 2 se ovim dokumentom smatra zatvorenom za planirani MVP scope.
