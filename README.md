# Yelp System — Microservices Architecture

Distribuirana microservices aplikacija za pretragu i preporuke poslovnih objekata na temelju Yelp Open Dataset.

---

## Arhitektura

```
Internet
    │
    ▼
 Nginx (:80)
    │
    ▼
API Gateway (:8000)
    │
    ├──► Business Service (:8001)  ◄──── PostgreSQL (:5432)
    │         │
    │         └── gRPC Server (:50051)
    │                    ▲
    └──► Recommendation Service (:8002)
              (gRPC client → business-service)

Ingestion Service (:8003) ──► PostgreSQL
```

### Servisi

| Servis | Port | Opis |
|---|---|---|
| **nginx** | 80 | Reverse proxy — ulazna točka |
| **api-gateway** | 8000 | HTTP proxy prema svim servisima |
| **business-service** | 8001 / 50051 | CRUD za poslovne objekte + gRPC server |
| **recommendation-service** | 8002 | Preporuke temeljene na kategorijama i lokaciji |
| **ingestion-service** | 8003 | Učitavanje JSON dataseta u PostgreSQL |
| **db (PostgreSQL)** | 5432 | Relacijska baza s 5 tablica |

---

## Struktura projekta

```
yelp-system/
├── docker-compose.yml              # Orkestracija svih servisa
├── requirements.txt                # Top-level Python ovisnosti
├── infrastructure/
│   ├── nginx/
│   │   └── nginx.conf              # Nginx reverse proxy konfiguracija
│   └── data/
│       └── raw/                    # Yelp JSON dataset datoteke (5 GB+)
│           ├── yelp_academic_dataset_business.json
│           ├── yelp_academic_dataset_review.json
│           ├── yelp_academic_dataset_user.json
│           ├── yelp_academic_dataset_tip.json
│           └── yelp_academic_dataset_checkin.json
├── services/
│   ├── api-gateway/
│   │   └── app/
│   │       ├── main.py             # FastAPI app, routing
│   │       ├── config.py           # Settings (BaseSettings)
│   │       ├── clients/            # httpx klijenti za downstream servise
│   │       │   ├── business_client.py
│   │       │   └── recommendation_client.py
│   │       └── routes/
│   │           ├── business.py
│   │           └── recommendation.py
│   ├── business-service/
│   │   └── app/
│   │       ├── main.py             # FastAPI app + gRPC thread
│   │       ├── grpc_server.py      # gRPC server (BusinessService)
│   │       ├── api/routes.py       # REST endpointovi
│   │       ├── core/config.py      # Settings
│   │       ├── db/session.py       # SQLAlchemy engine/session
│   │       ├── models/business.py  # ORM modeli (5 tablica)
│   │       ├── repository/         # SQL upiti
│   │       ├── service/            # Poslovna logika
│   │       └── grpc/               # Generirani protobuf stubs
│   ├── recommendation-service/
│   │   └── app/
│   │       ├── main.py
│   │       ├── algorithms/scoring.py      # Algoritam bodovanja kandidata
│   │       ├── clients/business_client.py # gRPC klijent
│   │       ├── service/recommendation_service.py
│   │       └── api/routes.py
│   └── ingestion-service/
│       └── app/
│           ├── main.py                         # FastAPI app s trigger endpointovima
│           ├── loaders/json_loader.py          # Generator učitavači (line-by-line)
│           ├── utils/parser.py                 # Parseri za svakih 5 entiteta
│           ├── service/ingestion_service.py    # Batch ingestion logika
│           ├── models.py                       # SQLAlchemy modeli
│           └── db/session.py
├── shared/
│   ├── protobuf/                   # .proto definicije
│   │   ├── business.proto
│   │   ├── recommendation.proto
│   │   └── common.proto
│   ├── generated/                  # Generirani gRPC stubs
│   ├── schemas/                    # Pydantic schemas
│   └── utils/
│       └── logger.py               # Centralni logger (get_logger)
└── services/
    ├── business-service/tests/test_business.py
    ├── recommendation-service/tests/test_recommendation.py
    ├── ingestion-service/tests/test_ingestion.py
    └── api-gateway/tests/test_gateway.py
```

---

## Baza podataka

PostgreSQL 15 s 5 tablica i ukupno **~10.2 milijuna zapisa**:

| Tablica | Zapisi | Indeksi |
|---|---|---|
| `businesses` | 150,346 | city, stars, (city, stars) |
| `users` | 1,987,897 | — |
| `reviews` | 6,990,280 | business_id, user_id, stars |
| `tips` | 908,915 | business_id, user_id |
| `checkins` | 131,930 | business_id |

---

## gRPC komunikacija

`recommendation-service` komunicira s `business-service` isključivo putem gRPC-a (port 50051).

Proto datoteke se nalaze u `shared/protobuf/`. Generirani stubs su kopirani u svaki servis koji ih koristi (`app/grpc/`).

**RPC metode (BusinessService):**
- `GetBusiness(BusinessRequest) → BusinessResponse`
- `ListBusinesses(ListBusinessesRequest) → ListBusinessesResponse`

---

## Nginx routing

| Path | Proksira na |
|---|---|
| `/` | api-gateway:8000 (sav javni promet) |
| `/internal/businesses/` | business-service:8001 (debug) |
| `/internal/recommendations/` | recommendation-service:8002 (debug) |
| `/internal/ingest/` | ingestion-service:8003 (admin) |

---

## Pokretanje

### Preduvjeti
- Docker Desktop
- Docker Compose v2

### Start (Docker)

```bash
docker compose up --build
```

### Lokalno pokretanje (development)

```bash
# Aktivacija virtualenv
.\venv\Scripts\Activate.ps1

# business-service
cd services/business-service
python -m uvicorn app.main:app --reload --port 8001

# ingestion-service
cd services/ingestion-service
python -m uvicorn app.main:app --reload --port 8003
```

---

## API endpointovi

### Javni (kroz Nginx + api-gateway)

```
GET  /api/businesses                          # lista poslovnih objekata
GET  /api/businesses?city=Phoenix&min_stars=4
GET  /api/businesses/{id}                     # detalji jednog objekta
GET  /api/recommendations/{id}                # preporuke za objekt
GET  /api/recommendations/{id}?limit=5
```

### business-service (port 8001)

```
GET  /businesses
GET  /businesses?city=Phoenix&min_stars=4&page=1&limit=20
GET  /businesses/{id}
```

### recommendation-service (port 8002)

```
GET  /recommendations/{business_id}
GET  /recommendations/{business_id}?limit=10
```

### ingestion-service (port 8003)

```
POST /ingest/all           # pokretanje ingestion svih dataseta (background)
POST /ingest/businesses
POST /ingest/reviews
POST /ingest/users
POST /ingest/tips
POST /ingest/checkins
```

---

## Testovi

Testovi se nalaze u `tests/` mapi svakog servisa i koriste `pytest` + `unittest.mock`. Downstream ovisnosti (DB, gRPC, HTTP) su u potpunosti mockirani.

```bash
# business-service
cd services/business-service
python -m pytest tests/ -v

# recommendation-service
cd services/recommendation-service
python -m pytest tests/ -v

# ingestion-service
cd services/ingestion-service
python -m pytest tests/ -v

# api-gateway
cd services/api-gateway
python -m pytest tests/ -v
```

---

## Logging

Svaki servis koristi centralni `get_logger(name)` iz `shared/utils/logger.py`. Logovi idu na stdout u formatu:

```
2026-04-15 16:40:50 | INFO | ingestion-service | Starting ingestion: tips
2026-04-15 16:41:56 | INFO | ingestion-service | Finished tips — total records: 908915
```

---

## Tehnički stack

| Komponenta | Tehnologija |
|---|---|
| Web framework | FastAPI 0.111 |
| ASGI server | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Baza | PostgreSQL 15 |
| gRPC | grpcio + grpcio-tools |
| HTTP klijent | httpx (async) |
| Reverse proxy | Nginx 1.25 (Alpine) |
| Konfiguracija | pydantic-settings |
| Testovi | pytest + unittest.mock |
| Kontejnerizacija | Docker + Docker Compose v2 |
