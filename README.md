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
* ✅ Business detail page (categories, location, status)
* ✅ Recommendation engine (distance + category + rating)
* ✅ Reviews system (paginated, sorted)
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

After startup:

| URL                             | Service           |
| ------------------------------- | ----------------- |
| http://localhost                | Nginx → Frontend  |
| http://localhost/api/businesses | API               |
| http://localhost:3000           | Frontend (direct) |

---

## 🧰 Tech Stack

| Layer      | Technology                 |
| ---------- | -------------------------- |
| Frontend   | Next.js, React, TypeScript |
| Backend    | FastAPI, Python            |
| Database   | PostgreSQL                 |
| ORM        | SQLAlchemy                 |
| RPC        | gRPC                       |
| Proxy      | Nginx                      |
| Containers | Docker                     |

---

## 🛠️ Future Improvements

* JWT authentication (API Gateway)
* Full-text search (PostgreSQL)
* Redis caching
* Map integration (Leaflet / Mapbox)
* CI/CD pipeline (GitHub Actions)

---

## 📡 API Endpoints

All external requests go through the **API Gateway** (`:8000`).

---

### 🏢 Business Endpoints

| Method | Endpoint                   | Description                                                      |
| ------ | -------------------------- | ---------------------------------------------------------------- |
| `GET`  | `/businesses`              | Search businesses (`?city=`, `?min_stars=`, `?page=`, `?limit=`) |
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

---

## 👤 Author

**Stjepan Velc**

Backend & System Design focused developer

**Tech stack:**
Python • FastAPI • Microservices • PostgreSQL

