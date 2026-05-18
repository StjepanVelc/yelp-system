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

## Faza 1 - Observability foundation

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

### CDC mapping
- businesses INSERT/UPDATE/DELETE:
  - invalidate yelp:prod:business:details:{id}:v1
  - invalidate yelp:prod:recommendation:by_business:{id}:*:v1
  - invalidate yelp:prod:business:cities:all:v1 samo kad se promijeni city ili is_open
- reviews INSERT/UPDATE/DELETE:
  - invalidate yelp:prod:recommendation:by_business:{business_id}:*:v1
- users:
  - trenutno no invalidation needed

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
