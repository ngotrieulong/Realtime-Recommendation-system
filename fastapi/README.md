# 🎬 Movie Recommendation API

A production-ready, high-performance Recommendation System API built with **FastAPI**.
It features a **Hybrid Recommendation Engine** blending Batch (Collaborative Filtering) and Real-time (Vector Similarity) approaches.

## 🚀 Key Features

-   **Hybrid Engine**: Weights Pre-computed Batch Recs (70%) with Real-time Content Recs (30%).
-   **High Performance**:
    -   **Redis Caching** (L1) for sub-millisecond serving.
    -   **AsyncPG** for non-blocking Database I/O.
-   **Robustness**:
    -   **Rate Limiting** (SlowAPI) to protect endpoints.
    -   **Circuit Breakers** (Fallbacks) for database/cache failures.
    -   **Deep Health Checks** (Postgres & Redis ping).
-   **Security**:
    -   **JWT Authentication** (OAuth2).
    -   **Argon2** Password Hashing.
-   **Observability**:
    -   **Structured JSON Logging**.
    -   **Prometheus Metrics** (`/metrics`).
    -   **Request Tracing** (Correlation IDs).

## 🛠 Tech Stack

-   **Framework**: FastAPI
-   **Database**: PostgreSQL + PGVector
-   **Cache**: Redis
-   **Message Queue**: Kafka (AIOKafka)
-   **Auth**: Python-Jose (JWT), Passlib (Argon2)
-   **Testing**: Pytest, Pytest-Asyncio, HTTPX

## 🏁 Quick Start

### 1. Prerequisites
-   Python 3.9+
-   PostgreSQL, Redis, Kafka running (Docker recommended).

### 2. Installation

```bash
cd fastapi
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file or export variables:

```bash
export POSTGRES_DSN="postgresql://user:pass@localhost:5432/movie_db"
export REDIS_URL="redis://localhost:6379"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
```

### 4. Run Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

-   **Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
-   **Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)

## 🧪 Testing

Run the full test suite (Unit + Integration):

```bash
pytest
```

## 📡 API Reference

### Authentication

-   `POST /auth/register`: Register a new user.
-   `POST /auth/login`: Get Access Token.

### Recommendations

-   `GET /api/recommendations`: Get personalized movies.
    -   *Query Params*: `user_id`, `limit`.
    -   *Headers*: `Authorization: Bearer <token>` (Optional/Required based on config).

### System

-   `GET /health`: Check service health (DB/Redis status).
-   `GET /metrics`: Prometheus metrics.

## 📂 Project Structure

Please refer to [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture diagrams and component breakdown.
