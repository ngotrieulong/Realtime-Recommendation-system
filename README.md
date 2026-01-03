# 🎬 Real-Time Movie Recommendation System
## Production-Ready Lambda Architecture with Airflow 3.x + Spark 3.5 + Kafka


A complete, production-ready movie recommendation system implementing Lambda Architecture for both real-time and batch processing.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Configuration](#-configuration)
- [Usage Examples](#-usage-examples)
- [Monitoring](#-monitoring)
- [Troubleshooting](#-troubleshooting)
- [Performance Tuning](#-performance-tuning)
- [Contributing](#-contributing)

---

## ✨ Features

### Real-Time Layer (Speed Layer)
- ⚡ **Sub-second latency**: User interactions processed in < 500ms
- 🎯 **Instant recommendations**: Updates recommendations within seconds of user action
- 📊 **Event streaming**: Kafka-based event processing with exactly-once semantics
- 💾 **Multi-tier caching**: Redis (L1) → Postgres (L2) → Batch (L3)

### Batch Layer
- 🔄 **Daily model training**: Collaborative filtering with ALS (Alternating Least Squares)
- 📈 **Historical analysis**: Process full user interaction history
- 🎓 **ML pipeline**: Complete MLOps workflow with model versioning
- 🗄️ **Data archival**: Automatic archival of old events to object storage

### Infrastructure
- 🐳 **Fully containerized**: Docker Compose orchestration
- 🏗️ **Production-ready**: Multi-architecture support (ARM64 + AMD64)
- 📊 **Monitoring-ready**: Health checks, metrics endpoints
- 🔒 **Security-hardened**: RBAC, secrets management, network isolation

---

## 🏗️ Architecture

### Full System Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                          │
│                      http://localhost:3000                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  React Application (Frontend)                                   │
│  ├─ Components: RecommendationPanel, MovieCard, Dashboard      │
│  ├─ State: userId, sessionId, recommendations[]                │
│  └─ API Client: Fetch to http://localhost/api/*                │
│                                                                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ HTTP Requests
                     │ (CORS: localhost:3000 allowed)
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                    🌐 NGINX API GATEWAY                         │
│                      http://localhost/ (Port 80)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ROUTING RULES:                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Pattern         Backend        Purpose                    │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ /api/*       →  FastAPI:8000   Main API                  │ │
│  │ /admin/*     →  Airflow:8080   Workflow UI               │ │
│  │ /storage/*   →  MinIO:9001     File storage              │ │
│  │ /docs        →  FastAPI:8000   API documentation         │ │
│  │ /health      →  Gateway        Health check              │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  FEATURES:                                                      │
│  ├─ 🛡️ Rate Limiting:    100 req/min per IP                   │
│  ├─ 🔒 CORS Handling:    Centralized policy                   │
│  ├─ 📝 Access Logging:   Detailed request logs                │
│  ├─ 🔐 Security Headers: X-Frame-Options, CSP, etc.           │
│  ├─ 📦 Compression:      gzip (90% size reduction)            │
│  ├─ ⚡ Connection Pool:  Keepalive to backends                │
│  └─ 🎯 Load Balancing:   (Future: Multiple FastAPI instances) │
│                                                                 │
└──┬──────────┬──────────┬─────────────────────────────────────┘
   │          │          │
   │          │          │ Internal Network (Docker)
   │          │          │
   ↓          ↓          ↓
┌──────────────────────────────────────────────────────────────────┐
│                        BACKEND SERVICES                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FastAPI Application Server (Port 8000)                    │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │  Endpoints:                                                 │ │
│  │  ├─ GET  /api/recommendations  (Hybrid L2+L3)              │ │
│  │  ├─ POST /api/events           (Kafka → Spark)             │ │
│  │  ├─ GET  /api/movies            (Browse catalog)           │ │
│  │  ├─ GET  /api/metrics           (CTR, cache stats)         │ │
│  │  └─ GET  /health                (Service status)           │ │
│  │                                                             │ │
│  │  Logic:                                                     │ │
│  │  ├─ L1 Cache Check (Redis)                                 │ │
│  │  ├─ L2 Realtime Compute (pgvector)                         │ │
│  │  ├─ L3 Batch Fallback (pre-computed)                       │ │
│  │  └─ Hybrid Blending (70% batch + 30% realtime)            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                  ↓                  ↓                  ↓         │
│                  │                  │                  │         │
│  ┌───────────────┼──────────────────┼──────────────────┼──────┐ │
│  │               ↓                  ↓                  ↓      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │ │
│  │  │   Redis      │  │  Postgres    │  │    Kafka     │   │ │
│  │  │  Port 6379   │  │  Port 5432   │  │  Port 29092  │   │ │
│  │  ├──────────────┤  ├──────────────┤  ├──────────────┤   │ │
│  │  │              │  │              │  │              │   │ │
│  │  │ L1 Cache     │  │ Tables:      │  │ Topics:      │   │ │
│  │  │ ├─ recs:*    │  │ ├─ movies    │  │ ├─ movie-evts│   │ │
│  │  │ └─ TTL: 1h   │  │ ├─ user_prof │  │ └─ Consumers:│   │ │
│  │  │              │  │ ├─ batch_recs│  │    Spark     │   │ │
│  │  │ Hit Rate:    │  │ ├─ rec_logs  │  │              │   │ │
│  │  │ ~85%         │  │ └─ rec_feed  │  │ Retention:   │   │ │
│  │  │              │  │              │  │ 7 days       │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │ │
│  │                            ↑                  ↑           │ │
│  └────────────────────────────┼──────────────────┼───────────┘ │
│                                │                  │             │
│              ┌─────────────────┴────────┬─────────┘             │
│              │                          │                       │
│              ↓                          ↓                       │
│  ┌────────────────────────┐  ┌────────────────────────┐        │
│  │  Apache Spark          │  │  Apache Airflow        │        │
│  │  (Master + Worker)     │  │  (Scheduler + Web)     │        │
│  ├────────────────────────┤  ├────────────────────────┤        │
│  │                        │  │                        │        │
│  │  Real-time Layer:      │  │  Batch Layer:          │        │
│  │  ├─ Streaming Job      │  │  ├─ DAG: batch_recs   │        │
│  │  │  (Kafka consumer)   │  │  │  Schedule: 2 AM    │        │
│  │  │  Interval: 5s       │  │  │                    │        │
│  │  │                     │  │  │  Tasks:            │        │
│  │  │  Updates:           │  │  │  1. Archive events │        │
│  │  │  2. Train ALS model│        │
│  │  │                     │  │  │  3. Generate recs  │        │
│  │  │                     │  │  │  4. Atomic swap    │        │
│  │  Batch Layer:          │  │  │  5. Invalidate L1  │        │
│  │  └─ ALS Training       │  │  │                    │        │
│     (nightly, triggered   │  │  └─ Port: 8080        │        │
│      by Airflow)          │  │                        │        │
│  │                        │  │  Accessed via:         │        │
│  │  Port: 7077 (master)   │  │  http://localhost/     │        │
│  │  Port: 8081 (worker)   │  │         admin/         │        │
│  └────────────────────────┘  └────────────────────────┘        │
│              ↓                                                  │
│              ↓                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │                    MinIO Object Storage                │    │
│  │                   Port 9000 (API)                      │    │
│  │                   Port 9001 (Console)                  │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                         │    │
│  │  Buckets:                                              │    │
│  │  ├─ lakehouse/                                         │    │
│  │  │  ├─ models/                (Trained ALS models)    │    │
│  │  │  │  └─ als_20250103_02am/                          │    │
│  │  │  ├─ archived-events/        (Historical data)      │    │
│  │  │  │  └─ 2025/01/03/events.parquet                   │    │
│  │  │  ├─ batch-recs-history/     (Daily snapshots)      │    │
│  │  │  └─ checkpoints/            (Spark state)          │    │
│  │  │                                                     │    │
│  │  Accessed via:                                         │    │
│  │  ├─ Internal: s3a://lakehouse/                        │    │
│  │  └─ External: http://localhost/storage/               │    │
│  │                                                         │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Request Flow with Gateway

**Example: Get Recommendations**

`TIMELINE: User requests personalized recommendations`

1.  **T=0ms | User's Browser**: `fetch('http://localhost/api/recommendations?user_id=user_123')`
2.  **T=5ms | Nginx Gateway (Port 80)**:
    *   CORS Check: Origin localhost:3000 → ✅ Allowed
    *   Rate Limit: IP 192.168.1.100 → 45/100 requests → ✅ OK
    *   Route Match: `/api/*` → FastAPI backend
    *   Proxy: `http://fastapi:8000/api/recommendations`
3.  **T=10ms | FastAPI (Port 8000)**:
    *   Check L1 Cache (Redis) → MISS
    *   Get L2 Realtime Recs (pgvector)
    *   Get L3 Batch Recs (Postgres)
    *   Blend Hybrid (70% batch + 30% realtime)
    *   Cache Result in Redis
    *   Log to recommendation_logs
4.  **T=100ms | FastAPI Response**:
    *   Returns JSON with recommendations and metadata.
5.  **T=105ms | Nginx Gateway**:
    *   Adds Security Headers
    *   Compresses Response (gzip)
    *   Logs Request
6.  **T=110ms | User's Browser**:
    *   Response received and UI renders.

### Gateway Benefits Illustrated

**Without Gateway (Before)**:
*   ❌ Frontend knows all backend URLs
*   ❌ Each service handles CORS independently
*   ❌ No centralized rate limiting
*   ❌ Security risk (all ports exposed)

**With Gateway (After)**:
*   ✅ Single URL (http://localhost)
*   ✅ Rate limiting & Logging
*   ✅ CORS centralized
*   ✅ Security headers & Compression

### Port Mapping with Gateway

| Port | Service | Accessible From | Purpose |
|------|---------|-----------------|---------|
| 80 | Nginx Gateway | External | **MAIN ENTRY POINT** |
| 3000 | React Frontend | External | User Interface |
| 8000 | FastAPI | Internal | API (via gateway) |
| 8080 | Airflow Web | Internal | Workflow UI (via gateway) |
| 9000 | MinIO API | Internal | Object storage (via gateway) |
| 9001 | MinIO Console | Internal | Storage UI (via gateway) |
| 5432 | Postgres | Internal | Database |
| 6379 | Redis | Internal | Cache |
| 29092| Kafka | Internal | Event stream |

### Security Layers

1.  **Layer 1: Network Isolation**: Frontend (Public) → Gateway (Bridge) → Backend (Private)
2.  **Layer 2: Gateway Policies**: Rate Limiting, CORS, Headers, Request Size
3.  **Layer 3: Application Security**: Input Validation, SQL Injection Protection
4.  **Layer 4: Data Security**: Password Auth, Access Keys

---

## 🚀 Quick Start

### Prerequisites

```bash
# Required
✅ Docker Desktop (with 8GB RAM allocated)
✅ Docker Compose V2+
✅ 20GB+ free disk space
✅ Mac M4 (ARM64) or Intel/AMD (AMD64)

# Verify installations
docker --version          # Should be 20.x+
docker compose version    # Should be 2.x+
```

### Installation (5 Minutes)

**Step 1: Clone Repository**
```bash
git clone <repository-url>
cd movie-recommendation-system
```

**Step 2: Configure Environment**
```bash
# Copy environment template
cp .env.example .env

# Edit .env file (optional, defaults work for local development)
vim .env
```

**Step 3: Start All Services**
```bash
# Start infrastructure
docker compose up -d

# Watch logs (optional)
docker compose logs -f
```

**Step 4: Wait for Health Checks** (2-3 minutes)
```bash
# Check service status
docker compose ps

# All services should show "healthy" status
```

**Step 5: Access UIs**

Open in browser:
```
🌐 Frontend App:     http://localhost:3000
🌐 API Gateway:      http://localhost/
   ├─ Docs:          http://localhost/docs
   ├─ Airflow:       http://localhost/admin
   └─ MinIO:         http://localhost/storage
```

### Verify Installation

```bash
# Test API Gateway health
curl http://localhost/health

# Expected response:
# Gateway OK

# Test recommendation endpoint via Gateway
curl "http://localhost/api/recommendations?user_id=test_user_1&limit=5"
```

---

## 📁 Project Structure

```
movie-recommendation-system/
│
├── docker-compose.yaml              # Main orchestration file
├── .env.example                     # Environment variables template
├── README.md                        # This file
│
├── api-gateway/                     # NGINX API Gateway
│   └── nginx.conf                   # Routing and security config
│
├── frontend/                        # React Application
│   ├── src/                         # Source code
│   └── Dockerfile                   # Frontend container
│
├── airflow/                         # Airflow 3.1.5 configuration
│   ├── Dockerfile                   # Custom Airflow image
│   └── config/
│       └── airflow.cfg              # Optional custom config
│
├── dags/                            # Airflow DAGs
│   ├── batch_recommendation_dag.py  # Daily batch processing
│   └── model_training_dag.py        # ML model training
│
├── spark/                           # Spark 3.5.3 configuration
│   └── Dockerfile                   # Custom Spark image
│
├── spark-jobs/                      # Spark applications
│   ├── streaming_recommendations.py # Real-time processing
│   └── batch_model_training.py      # Batch ML training
│
├── fastapi/                         # API application
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                  # FastAPI application
│       ├── config.py                # Configuration
│       └── models.py                # Pydantic models
│
├── init-scripts/                    # Database initialization
│   └── init-pgvector.sql            # PostgreSQL schema
│
└── docs/                            # Documentation
    ├── QUICK_START_GUIDE.md
    ├── AIRFLOW_3X_MIGRATION_GUIDE.md
    └── DOCKERFILE_FIXES_CHANGELOG.md
```

---

## ⚙️ Configuration

### Resource Allocation (8GB Docker Memory)

Default allocation optimized for Mac M4 16GB (8GB Docker limit):

| Service          | Memory | CPUs | Purpose                    |
|------------------|--------|------|----------------------------|
| Spark Worker     | 1.5GB  | 2.0  | Data processing            |
| Kafka            | 768MB  | 1.0  | Message broker             |
| Postgres         | 512MB  | 0.5  | Database                   |
| MinIO            | 512MB  | 0.5  | Object storage             |
| Airflow Web      | 512MB  | 0.5  | UI                         |
| Airflow Scheduler| 512MB  | 0.5  | Orchestration              |
| Redis            | 256MB  | 0.25 | Cache                      |
| FastAPI          | 256MB  | 0.5  | API                        |
| Spark Master     | 256MB  | 0.5  | Coordinator                |
| Zookeeper        | 256MB  | 0.25 | Kafka coordination         |
| Nginx Gateway    | 128MB  | 0.25 | API Gateway                |
| Frontend         | 128MB  | 0.25 | UI                         |

**Total: ~5.6GB** (2.4GB buffer for system)

### Environment Variables

Key variables in `.env`:

```bash
# Performance tuning
AIRFLOW__CORE__PARALLELISM=32              # Concurrent tasks
SPARK_WORKER_MEMORY=1536m                  # Spark worker RAM
POSTGRES_MAX_CONNECTIONS=150               # DB connections

# Security (CHANGE IN PRODUCTION!)
AIRFLOW__CORE__FERNET_KEY=<generate-new>
POSTGRES_PASSWORD=<strong-password>
MINIO_ROOT_PASSWORD=<strong-password>

# Application settings
RECOMMENDATION_CACHE_TTL=3600              # Cache TTL (seconds)
SPARK_STREAMING_BATCH_INTERVAL=5           # Micro-batch interval
```

See `.env.example` for full list of options.

---

## 📖 Usage Examples

### Send User Interaction Event

```bash
# User clicks on "Inception"
curl -X POST http://localhost/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "movie_id": "m002",
    "event_type": "click"
  }'

# Response: {"status":"accepted","message":"Event queued for processing"}
```

### Get Recommendations

```bash
# Get top 10 recommendations for user
curl "http://localhost/api/recommendations?user_id=user_123&limit=10"

# Response:
# {
#   "user_id": "user_123",
#   "recommendations": [
#     {"movie_id":"m003","title":"Interstellar","score":0.94},
#     ...
#   ],
#   "source": "redis_cache",
#   "generated_at": "2025-01-01T00:00:00Z"
# }
```

### Start Spark Streaming Job

```bash
# Submit streaming job to Spark cluster
docker exec -it spark-master \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  /opt/spark-jobs/streaming_recommendations.py

# Monitor in Spark UI: http://localhost:8088
```

### Trigger Airflow DAG

```bash
# Via CLI
docker exec -it airflow-webserver \
  airflow dags trigger batch_recommendation_processing

# Or via UI: http://localhost/admin
# Navigate to DAGs → batch_recommendation_processing → Trigger DAG
```

---

## 📊 Monitoring

### Health Checks

```bash
# All services health
./scripts/health_check.sh

# Individual service health
curl http://localhost/health          # Gateway
curl http://localhost/api/health      # FastAPI (via Gateway)
curl http://localhost/admin/health    # Airflow (via Gateway)
```

### Metrics

```bash
# FastAPI metrics
curl http://localhost/api/metrics

# Example response:
# {
#   "total_requests": 15234,
#   "cache_hit_rate": 0.87,
#   "avg_response_time_ms": 12.3
# }
```

### Logs

```bash
# View all logs
docker compose logs -f

# Service-specific logs
docker compose logs -f fastapi
docker compose logs -f airflow-scheduler
docker compose logs -f spark-worker
docker compose logs -f nginx
docker compose logs -f frontend

# Airflow task logs
docker exec airflow-webserver \
  airflow tasks logs batch_recommendation_processing <task_id> <execution_date>
```

---

## 🔧 Troubleshooting

### Services Won't Start

```bash
# Check Docker resources
docker system df
docker stats

# Clean up
docker system prune -f
docker volume prune -f

# Restart services
docker compose down
docker compose up -d
```

### Health Checks Failing

**Problem**: Container marked as "unhealthy"

```bash
# Check specific service logs
docker logs kafka

# Common issues:
# 1. Kafka: Wait 30+ seconds for full startup
# 2. Postgres: Database still initializing
# 3. Airflow: DB migration in progress

# Solution: Wait and check again
docker compose ps
```

### Out of Memory Errors

**Problem**: `OOMKilled` or `java.lang.OutOfMemoryError`

```bash
# Check Docker memory limit
docker info | grep Memory

# Solution 1: Increase Docker memory (Docker Desktop → Settings)
# Solution 2: Reduce memory allocation in docker-compose.yaml
```

### Spark Job Failures

**Problem**: Spark jobs fail with connection errors

```bash
# Verify Spark cluster health
curl http://localhost:8088

# Check if worker is registered
# UI should show 1 worker with 2 cores, 1.5GB memory

# Common issues:
# 1. JAVA_HOME not set → Check Spark Dockerfile
# 2. JAR conflicts → Verify hadoop-aws versions match
# 3. Memory exceeded → Reduce executor memory

# Test Spark submit
docker exec spark-master \
  /opt/spark/bin/spark-submit \
  --version
```

### Database Connection Issues

```bash
# Test Postgres connection
docker exec -it postgres \
  psql -U airflow -d moviedb -c "SELECT COUNT(*) FROM movies;"

# Test from FastAPI container
docker exec -it fastapi \
  python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://airflow:airflow@postgres:5432/moviedb'))"
```

---

## 🎯 Performance Tuning

### For Higher Throughput

```yaml
# In .env or docker-compose.yaml
environment:
  # Increase parallelism
  - AIRFLOW__CORE__PARALLELISM=64
  - AIRFLOW__SCHEDULER__MAX_TIS_PER_QUERY=512
  
  # More Spark resources
  - SPARK_WORKER_MEMORY=4g
  - SPARK_WORKER_CORES=4
  
  # More database connections
  - POSTGRES_MAX_CONNECTIONS=300
  - AIRFLOW__DATABASE__SQL_ALCHEMY_POOL_SIZE=20
```

### For Lower Latency

```yaml
# Reduce batch intervals
environment:
  - SPARK_STREAMING_BATCH_INTERVAL=2  # From 5s to 2s
  
# More aggressive caching
  - RECOMMENDATION_CACHE_TTL=7200  # 2 hours
  
# Increase Redis memory
  - REDIS_MAX_MEMORY=512mb
```

### For Better Accuracy

```yaml
# Longer model training
environment:
  - ALS_MAX_ITER=20        # From 10 to 20
  - ALS_RANK=20            # More latent factors
  - RECOMMENDATION_TOP_N=100  # Generate more candidates
```

---

## 📝 Development

### Running Tests

```bash
# Unit tests
docker exec fastapi pytest tests/

# Integration tests
docker exec airflow-webserver \
  airflow dags test batch_recommendation_processing 2025-01-01
```

### Hot Reload (Development Mode)

FastAPI and Airflow DAGs support hot reload:

```bash
# Edit files locally
vim fastapi/app/main.py
vim dags/batch_recommendation_dag.py

# Changes apply immediately (mounted volumes)
# No need to rebuild containers
```

### Rebuilding After Code Changes

```bash
# Rebuild specific service
docker compose build airflow-webserver
docker compose up -d airflow-webserver

# Rebuild all
docker compose build
docker compose up -d
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- Apache Airflow team for the excellent 3.x release
- Apache Spark community
- pgvector maintainers
- FastAPI creator Sebastián Ramírez

---

## 📚 Additional Documentation

- [Airflow 3.x Migration Guide](docs/AIRFLOW_3X_MIGRATION_GUIDE.md)
- [Dockerfile Fixes Changelog](docs/DOCKERFILE_FIXES_CHANGELOG.md)
- [Quick Start Guide](docs/QUICK_START_GUIDE.md)

---

**Built with ❤️ for production ML systems**