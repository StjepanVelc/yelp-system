# Implementation Plan - production nadogradnje

Ovo je izvedbeni plan za upgrade postojeceg Yelp microservices setupa.
Redoslijed je fiksan i ostaje:

1. Observability foundation
2. Cache hardening
3. Debezium + Kafka CDC invalidation
4. Load testing + dashboards

Globalne granice scopea:
- PostgreSQL je source of truth.
- Redis je advisory cache.
- Search rezultati nisu cacheirani i ne ulaze u CDC invalidation scope.

Namjena ovog dokumenta:
- plan i scope po fazama
- rizici, verification checklist i "sto ne raditi"
- bez detaljnog post-implementation izvjestaja

## Faza 1 - Observability foundation

### Status
- Plan baseline i scope reference

### Cilj
Postaviti minimalni, ali koristan observability baseline kroz sve servise da odmah vidimo request flow, greske i latencije.

### Minimalni MVP scope
- correlation ID middleware kroz gateway i backend servise
- structured logs (konzistentna polja)
- OpenTelemetry traces prema Jaegeru
- Prometheus metrics + /metrics endpoint po servisu
- osnovni Grafana dashboard (RPS, error rate, p95)

### Konkretne datoteke
- services/api-gateway/app/main.py
- services/api-gateway/app/logger.py
- services/business-service/app/main.py
- services/business-service/app/core/logger.py
- services/recommendation-service/app/main.py
- services/recommendation-service/app/core/logger.py
- services/ingestion-service/app/main.py
- services/ingestion-service/app/core/logger.py
- docker-compose.yml

### Rizici
- veci log volume i storage trosak
- previsoka metric cardinality
- tracing overhead pod jacim loadom

### Verification checklist
- svaki servis vraca 200 na /metrics
- correlation_id se vidi kroz gateway -> downstream logove
- barem jedan end-to-end trace je vidljiv u Jaegeru
- Grafana ima RPS, error rate i p95 po servisu

### Sto ne raditi u ovoj fazi
- ne dirati poslovnu logiku endpointa
- ne uvoditi napredni sampling policy po endpointu
- ne raditi veliki tracing redesign

## Faza 2 - Cache hardening

### Status
- Plan baseline i scope reference

### Cilj
Ucvrstiti i izmjeriti postojeci Redis cache-aside bez promjene postojece semantike.

### Minimalni MVP scope
- dokumentirati trenutni cache contract i key namespace
- mjeriti hit/miss/error, cache latency i invalidation count
- zadrzati trenutne TTL vrijednosti i jitter
- zadrzati fallback invalidation
- jasno zapisati da Redis nije source of truth

### Konkretne datoteke
- services/business-service/app/core/cache.py
- services/business-service/app/service/business_service.py
- services/business-service/app/api/routes.py
- services/recommendation-service/app/core/cache.py
- services/recommendation-service/app/service/recommendation_service.py
- services/recommendation-service/app/api/routes.py
- docs/redis-cache.md
- docs/redis-runbook.md

### Rizici
- metrike mogu izgledati dobro, a ne pokrivati sve grane
- stale cache je i dalje moguc do TTL isteka (ocekivano)

### Verification checklist
- /cache/stats daje konzistentan hit/miss/error po namespaceu
- cache latency je mjerljiv i citljiv
- invalidation count raste na write triggerima
- TTL ponasanje potvrdeno za details/cities/recommendation kljuceve

### Sto ne raditi u ovoj fazi
- ne uvoditi cache za search rezultate
- ne uvoditi write-through ili write-back
- ne raditi globalni key schema refactor

## Faza 3 - Debezium + Kafka CDC invalidation

### Status
- Plan baseline i scope reference

### Cilj
Uvesti event-driven invalidation Redis kljuceva na promjene u tablicama businesses i reviews.

### Minimalni MVP scope
- Kafka + Debezium connector + CDC consumer
- invalidation po mapiranju za businesses i reviews
- snapshot strategija: fokus na nove promjene nakon dizanja pipelinea
- consumer offset za MVP: latest

### PostgreSQL WAL konfiguracija (obavezno)
U docker-compose.yml koristiti command override:

postgres -c wal_level=logical -c max_wal_senders=10 -c max_replication_slots=10

POSTGRES_INITDB_ARGS se ne koristi u ovom planu.

### Payload shape za CDC consumer

Consumer treba raditi s minimalnim, stabilnim shape-om koji se može izvesti iz Debezium eventa.

#### Raw Debezium signal koji je bitan

- `op`: `c`, `u`, `d`, `r`
- `source.table`
- `source.ts_ms`
- `before`
- `after`

#### Normalizirani interni event koji consumer koristi

```json
{
  "table": "businesses",
  "op": "u",
  "entity_id": "business_id_or_review_id",
  "business_id": null,
  "changed_fields": ["city", "is_open"],
  "before": {},
  "after": {}
}
```

#### Minimalna pravila po tablici

- `businesses`
  - `entity_id` = `id`
  - `changed_fields` se računa usporedbom `before` i `after`
  - za `u` evente consumer mora znati jesu li promijenjeni `city` ili `is_open`
  - `business_id` nije potreban jer je `id` jedini ključ
- `reviews`
  - `entity_id` = `review_id`
  - `business_id` se čita iz `after.business_id`, a za delete iz `before.business_id`
  - za invalidaciju je dovoljno znati koji business je pogođen, ne treba kompletan review payload
- `r` eventi
  - u MVP-u se ignoriraju za invalidaciju
  - cilj je reagirati samo na stvarne promjene, ne na snapshot/backfill noise

#### Što consumer smije pretpostaviti

- `before` može biti `null` kod create eventa
- `after` može biti `null` kod delete eventa
- ako `business_id` nije dostupan u `after`, consumer ga mora uzeti iz `before`
- za `businesses` update consumer ne mora znati sve kolone, samo one koje utječu na mapping

### CDC mapping
- businesses INSERT/UPDATE/DELETE:
  - invalidate yelp:prod:business:details:{id}:v1
  - invalidate yelp:prod:recommendation:by_business:{id}:*:v1
  - invalidate yelp:prod:business:cities:all:v1 samo kad se promijeni city ili is_open
- reviews INSERT/UPDATE/DELETE:
  - invalidate yelp:prod:recommendation:by_business:{business_id}:*:v1
- users:
  - trenutno no invalidation needed

### Bitna odluka za reviews

- Reviews su zaseban invalidation problem od businesses.
- U trenutnom modelu reviews se upisuju u `reviews` tablicu, a business details se čitaju iz `businesses` tablice.
- `businesses.review_count` i `businesses.stars` su već denormalizirane kolone u source tablici, ali u postojećem write pathu reviews ih ne ažurira.
- Zato za MVP reviews CDC invalidira samo recommendation cache.
- Business details cache se invalidira iz CDC-a samo ako business event stvarno mijenja `businesses` red, ili ako kasnije uvedemo write path koji iz reviews re-računa agregate u `businesses`.
- Ako se u budućnosti doda automatsko re-računavanje `review_count` i `stars` na review write, tada treba proširiti mapping i invalidirati i `business.details:{id}:v1`.

Redis delete je idempotentan:
- delete existing key = OK
- delete missing key = OK/no-op

### Konkretne datoteke i direktoriji
- services/cdc-consumer/
- infrastructure/debezium/
- infrastructure/kafka/
- docker-compose.yml
- docs/redis-runbook.md
- docs/environment-variables.md

### Rizici
- ako CDC consumer propusti event, Redis moze ostati stale do TTL isteka
- zato TTL i fallback invalidation moraju ostati aktivni
- latest offset preskace stare evente prije starta consumera (prihvaceno za MVP)

### Verification checklist
- Debezium connector je healthy i emitira events
- CDC consumer prima evente i radi invalidation
- businesses city/is_open promjena invalidira cities key
- search endpointi rade neovisno o CDC invalidationu
- simulirani outage consumera pokazuje stale window ogranicen TTL-om

### Sto ne raditi u ovoj fazi
- ne uvoditi search invalidation
- ne uvoditi full replay/backfill kao MVP uvjet
- ne uvoditi striktni exactly-once requirement u MVP

### Pre-flight checklist prije starta

#### Preporučeni redoslijed rada

1. Podesiti PostgreSQL za logical replication i dodati Kafka/Debezium infrastrukturu u `docker-compose.yml`.
2. Dodati `services/cdc-consumer/` kao zaseban servis ili modul i spojiti ga na Kafka topic.
3. Dodati environment varijable i dokumentirati ih u `docs/environment-variables.md`.
4. Definirati payload shape i točan invalidation mapping za `businesses` i `reviews`.
5. Dodati fallback ponašanje za outage/restart i tek onda end-to-end testove.

#### Konkretni taskovi po datotekama

- `docker-compose.yml`:
  - Kafka broker
  - Debezium connect servis
  - CDC consumer servis
  - PostgreSQL command override za logical replication
- `services/cdc-consumer/`:
  - consumer bootstrap
  - Kafka subscription
  - event parsing i routing po tablici
  - Redis invalidation pozivi
- `docs/environment-variables.md`:
  - CDC-specific env varovi
  - Kafka bootstrap server, topic imena, consumer group, polling timeout
- `docs/redis-runbook.md`:
  - CDC outage procedure
  - očekivano stale window ponašanje

#### Definition of Ready za Fazu 3

- [x] Infrastruktura za Kafka i Debezium postoji u compose setupu
- [x] PostgreSQL ima logical replication postavke
- [x] CDC consumer može startati lokalno bez ručnih koraka
- [x] Known topic names i payload schema su zapisani
- [x] Invalidation mapping za `businesses` i `reviews` je jednoznačan
- [x] Fallback ponašanje za consumer outage je definirano
- [x] Jedan minimalni E2E test ili smoke test je dodan

#### Finalni MVP scope za Fazu 3

- PostgreSQL logical replication je uključena i dokumentirana.
- Kafka i Debezium pipeline su dostupni kroz lokalni compose setup.
- CDC consumer sluša evente i invalidira Redis ključeve.
- `businesses` eventi invalidiraju `business.details`, `business.cities` i `recommendation.by_business`.
- `reviews` eventi invalidiraju samo `recommendation.by_business`.
- Business details cache se ne invalidira na review evente dok reviews ne počnu mijenjati business agregate.
- Outage consumer-a ostaje fail-safe kroz TTL i postojeći fallback invalidation.
- Search cache i search invalidation ostaju izvan scopea.

## Faza 4 - Load testing + dashboards

### Cilj
Izmjeriti stvarni efekt faza 1-3 kroz reproducibilne testove i dashboarde.

### Minimalni MVP scope
- k6 ili Locust scenariji (steady + burst)
- Grafana dashboardi: p50/p95/p99, error rate, RPS, cache hit-rate
- baseline vs post-upgrade usporedba

### Konkretne datoteke
- scripts/cache_load_test.py
- scripts/traffic_dashboard.py
- scripts/traffic_live_monitor.py
- docs/testing-lan.md
- docs/testing-traffic-live.md
- docs/redis-cache.md
- docker-compose.yml

### Rizici
- workload profil moze biti nereprezentativan
- dashboard bez jasnih pragova lako zavede

### Verification checklist
- test runovi su reproducibilni
- dashboard pokazuje p50/p95/p99, RPS, error rate, cache hit-rate
- postoji dokumentirana usporedba prije/poslije

### Sto ne raditi u ovoj fazi
- ne stavljati full chaos suite kao release gate
- ne siriti MVP na kompleksne frontend synthetic journeys
