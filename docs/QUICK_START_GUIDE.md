# 🚀 QUICK START GUIDE - REAL-TIME MOVIE RECOMMENDATION SYSTEM

═══════════════════════════════════════════════════════════════════

## 📁 PROJECT STRUCTURE

```
project-root/
│
├─ docker-compose.unified.yaml    # Main orchestration file
│
├─ init-scripts/
│  └─ init-pgvector.sql           # Database initialization
│
├─ spark/
│  └─ Dockerfile                  # Spark container image
│
├─ spark-jobs/
│  └─ streaming_recommendations.py # Real-time processing job
│
├─ airflow/
│  ├─ Dockerfile                  # Airflow container image
│  ├─ logs/                       # Task execution logs (auto-created)
│  └─ plugins/                    # Custom operators (optional)
│
├─ dags/
│  └─ (your batch ETL DAGs)       # Airflow workflows
│
├─ fastapi/
│  ├─ Dockerfile                  # FastAPI container image
│  ├─ requirements.txt            # Python dependencies
│  └─ app/
│     └─ main.py                  # API application
│
└─ REAL_TIME_LAYER_GUIDE.md       # Architecture documentation

```

═══════════════════════════════════════════════════════════════════

## ⚡ 5-MINUTE SETUP

═══════════════════════════════════════════════════════════════════

### Step 1: Prerequisites

Đảm bảo anh đã có:
```bash
✅ Docker Desktop (with 8GB RAM allocated)
✅ Docker Compose V2
✅ At least 20GB free disk space
✅ Mac M4 (hoặc tương tự)

# Verify installations
docker --version          # Should be 20.x or higher
docker compose version    # Should be 2.x
```

---

### Step 2: Project Setup

```bash
# Create project directory
mkdir -p ~/movie-recommendation-system
cd ~/movie-recommendation-system

# Create all required subdirectories
mkdir -p spark spark-jobs airflow/logs airflow/plugins dags fastapi/app init-scripts

# Copy all files from Claude's output into corresponding directories
# (Files are ready in /home/claude/)
```

---

### Step 3: Launch the System

```bash
# Start all services
docker compose -f docker-compose.unified.yaml up -d

# Wait for services to be healthy (~2-3 minutes)
# You can monitor progress with:
docker compose ps
```

Expected output when all services are ready:
```
NAME              STATUS                    PORTS
─────────────────────────────────────────────────────────────────
minio             Up (healthy)              9000-9001
postgres          Up (healthy)              5432
redis             Up (healthy)              6379
zookeeper         Up (healthy)              2181
kafka             Up (healthy)              9092
kafka-ui          Up                        8081
spark-master      Up (healthy)              7077, 8088
spark-worker      Up                        8089
airflow-webserver Up (healthy)              8080
airflow-scheduler Up                        -
fastapi           Up (healthy)              8000
```

---

### Step 4: Verify Installation

Open these URLs in browser:

```
┌──────────────────────┬─────────────────────────────────────┐
│ Service              │ URL                                 │
├──────────────────────┼─────────────────────────────────────┤
│ FastAPI Docs         │ http://localhost:8000/docs          │
│ FastAPI Health       │ http://localhost:8000/health        │
│ Airflow UI           │ http://localhost:8080               │
│                      │ (admin/admin)                       │
│ Spark Master UI      │ http://localhost:8088               │
│ Kafka UI             │ http://localhost:8081               │
│ MinIO Console        │ http://localhost:9001               │
│                      │ (minioadmin/minioadmin)             │
└──────────────────────┴─────────────────────────────────────┘
```

All pages should load successfully! ✅

═══════════════════════════════════════════════════════════════════

## 🧪 TESTING THE PIPELINE

═══════════════════════════════════════════════════════════════════

### Test 1: Send a User Event

```bash
# Simulate user clicking on "Inception"
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_1",
    "movie_id": "m002",
    "event_type": "click"
  }'

# Expected response:
{
  "status": "accepted",
  "message": "Event queued for processing",
  "timestamp": "2024-01-15T20:30:45.123456"
}
```

### Test 2: Start Spark Streaming Job

```bash
# Submit streaming job to Spark cluster
docker exec -it spark-master \
  /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark-jobs/streaming_recommendations.py

# You should see logs:
🚀 Starting Real-Time Recommendation Engine
📡 Kafka: kafka:29092, Topic: movie-events
✅ Streaming job started successfully. Processing events...
```

**IMPORTANT**: Keep this terminal open! Streaming job runs continuously.

### Test 3: Verify Event Processing

```bash
# Open Kafka UI: http://localhost:8081
# Navigate to: Topics → movie-events → Messages

# You should see your event:
{
  "event_id": "abc-123-...",
  "user_id": "test_user_1",
  "movie_id": "m002",
  "event_type": "click",
  "timestamp": "2024-01-15T20:30:45Z"
}
```

### Test 4: Check Recommendations

```bash
# Wait 5-10 seconds for processing, then:
curl "http://localhost:8000/api/recommendations?user_id=test_user_1&limit=5"

# Expected response:
{
  "user_id": "test_user_1",
  "recommendations": [
    {
      "movie_id": "m003",
      "title": "Interstellar",
      "genres": ["Sci-Fi", "Drama"],
      "score": 0.94
    },
    ...
  ],
  "source": "redis_cache",  # or "postgres_realtime"
  "generated_at": "2024-01-15T20:30:50.123456"
}
```

### Test 5: Load Testing (Optional)

```bash
# Install test tool
pip install httpie

# Send 100 events rapidly
for i in {1..100}; do
  http POST localhost:8000/api/events \
    user_id="user_$i" \
    movie_id="m$((RANDOM % 5 + 1))" \
    event_type=click &
done

# Check metrics
http localhost:8000/metrics

# Expected output:
{
  "total_requests": 100,
  "cache_hit_rate": 0.75,
  "avg_response_time_ms": 15.3
}
```

═══════════════════════════════════════════════════════════════════

## 🛠️ COMMON OPERATIONS

═══════════════════════════════════════════════════════════════════

### View Logs

```bash
# All services
docker compose -f docker-compose.unified.yaml logs -f

# Specific service
docker compose -f docker-compose.unified.yaml logs -f fastapi
docker compose -f docker-compose.unified.yaml logs -f kafka
docker compose -f docker-compose.unified.yaml logs -f spark-worker

# Spark Streaming job (if running in container)
docker logs -f spark-worker | grep "Processing micro-batch"
```

### Restart Services

```bash
# Restart single service
docker compose -f docker-compose.unified.yaml restart fastapi

# Restart all services
docker compose -f docker-compose.unified.yaml restart

# Full rebuild (after code changes)
docker compose -f docker-compose.unified.yaml up -d --build
```

### Access Database

```bash
# Connect to Postgres
docker exec -it postgres psql -U airflow -d moviedb

# Useful queries:
\dt                                    # List tables
SELECT COUNT(*) FROM movies;           # Check movie count
SELECT COUNT(*) FROM rt_user_interactions;  # Check events
SELECT * FROM user_profiles LIMIT 5;   # View user vectors

# Check pgvector
SELECT movie_id, title FROM movies WHERE embedding IS NOT NULL LIMIT 3;
```

### Access Redis

```bash
# Connect to Redis
docker exec -it redis redis-cli

# Useful commands:
KEYS recs:*                    # List all cached recommendations
GET recs:test_user_1           # View specific user's cache
TTL recs:test_user_1           # Check expiration time
DBSIZE                         # Total keys in cache
INFO memory                    # Memory usage
```

### Check Kafka Topics

```bash
# List topics
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe topic
docker exec -it kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic movie-events

# Consume messages (real-time monitoring)
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic movie-events \
  --from-beginning
```

### Stop System

```bash
# Stop all services (preserves data)
docker compose -f docker-compose.unified.yaml stop

# Stop and remove containers (preserves volumes)
docker compose -f docker-compose.unified.yaml down

# Complete cleanup (⚠️ DELETES ALL DATA)
docker compose -f docker-compose.unified.yaml down -v
```

═══════════════════════════════════════════════════════════════════

## 🐛 TROUBLESHOOTING

═══════════════════════════════════════════════════════════════════

### Problem: Services won't start

```bash
# Check Docker resources
docker system df                 # Disk usage
docker stats                     # Memory/CPU usage

# Common fixes:
docker system prune -f           # Clean unused containers
docker volume prune -f           # Clean unused volumes
```

### Problem: Kafka connection errors

```bash
# Verify Kafka is ready
docker logs kafka | grep "started"

# Should see:
[KafkaServer id=1] started (kafka.server.KafkaServer)

# If not, wait 30 more seconds or restart:
docker compose restart kafka
```

### Problem: Spark Streaming job crashes

```bash
# Check worker logs
docker logs spark-worker

# Common issues:
1. OutOfMemoryError → Reduce batch size in streaming job
2. Connection timeout → Kafka/Postgres not ready, wait and retry
3. Import errors → Missing dependencies, rebuild container
```

### Problem: FastAPI returns 500 errors

```bash
# Check API logs
docker logs fastapi

# Test database connection
docker exec -it fastapi python -c "
import asyncpg
import asyncio
async def test():
    conn = await asyncpg.connect('postgresql://airflow:airflow@postgres:5432/moviedb')
    print(await conn.fetchval('SELECT 1'))
asyncio.run(test())
"

# Should print: 1
```

### Problem: No recommendations returned

```bash
# Check if sample data loaded
docker exec -it postgres psql -U airflow -d moviedb -c \
  "SELECT COUNT(*) FROM movies;"

# Should be > 0

# If 0, re-run initialization:
docker exec -it postgres psql -U airflow -d moviedb \
  -f /docker-entrypoint-initdb.d/01-init-pgvector.sql
```

═══════════════════════════════════════════════════════════════════

## 📊 MONITORING DASHBOARD

═══════════════════════════════════════════════════════════════════

### Health Check Dashboard

Create a simple monitoring script:

```bash
#!/bin/bash
# health_check.sh

echo "🏥 System Health Check"
echo "═════════════════════════════════════════"

# FastAPI
echo -n "FastAPI:    "
curl -s http://localhost:8000/health | jq -r '.status' || echo "❌ DOWN"

# Airflow
echo -n "Airflow:    "
curl -s http://localhost:8080/health | jq -r '.status' || echo "❌ DOWN"

# Spark
echo -n "Spark:      "
curl -s http://localhost:8088 > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Kafka
echo -n "Kafka UI:   "
curl -s http://localhost:8081 > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Postgres
echo -n "Postgres:   "
docker exec postgres pg_isready -U airflow > /dev/null && echo "✅ UP" || echo "❌ DOWN"

# Redis
echo -n "Redis:      "
docker exec redis redis-cli ping | grep -q PONG && echo "✅ UP" || echo "❌ DOWN"

echo "═════════════════════════════════════════"

# Performance Metrics
echo ""
echo "📈 Performance Metrics"
echo "─────────────────────────────────────────"
curl -s http://localhost:8000/metrics | jq '.'
```

Run it:
```bash
chmod +x health_check.sh
./health_check.sh
```

═══════════════════════════════════════════════════════════════════

## 🎯 NEXT STEPS

═══════════════════════════════════════════════════════════════════

### Phase 1: Enhancements (Week 1-2)
```
├─ Add more sophisticated recommendation algorithms
├─ Implement A/B testing framework
├─ Add real movie dataset (MovieLens, TMDB)
└─ Create simple web UI for testing
```

### Phase 2: Production Hardening (Week 3-4)
```
├─ Add authentication (JWT)
├─ Implement monitoring (Prometheus + Grafana)
├─ Set up CI/CD pipeline
└─ Write comprehensive tests
```

### Phase 3: Scale & Optimize (Week 5-6)
```
├─ Add auto-scaling for Spark workers
├─ Implement model versioning (MLflow)
├─ Optimize vector search (tune HNSW params)
└─ Deploy to cloud (AWS/GCP)
```

═══════════════════════════════════════════════════════════════════

Anh Long ơi, system đã sẵn sàng! 🎉

Giờ anh có thể:
1. ✅ Start entire system với 1 command
2. ✅ Send events và see real-time recommendations
3. ✅ Monitor via multiple UIs
4. ✅ Scale components independently
5. ✅ Debug issues với detailed logs

Hãy test thử và cho tôi biết nếu anh cần clarification hoặc thêm features nào nhé! 🚀