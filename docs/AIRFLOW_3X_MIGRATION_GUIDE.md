# 🔄 AIRFLOW 2.x → 3.x MIGRATION GUIDE

═══════════════════════════════════════════════════════════════════

## 📋 TÓM TẮT - Những gì thay đổi

Anh Long ơi, đây là những thay đổi QUAN TRỌNG khi upgrade từ Airflow 2.8.1 → 3.1.5:

### ✅ GOOD NEWS - Mostly Backward Compatible

Airflow team đã rất cẩn thận với breaking changes. Đa số DAGs từ 2.x sẽ chạy OK trên 3.x với minimal modifications. Nhưng vẫn có một số điểm cần update.

═══════════════════════════════════════════════════════════════════

## 🔧 PART 1: DOCKER-COMPOSE CHANGES

═══════════════════════════════════════════════════════════════════

### 1.1 Environment Variables Updated

```yaml
# ❌ REMOVED (no longer needed in Airflow 3.x):
- AIRFLOW__WEBSERVER__RBAC=True  # RBAC is MANDATORY in 3.x
- AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True  # Default changed to False

# ✅ KEEP (still valid):
- AIRFLOW__CORE__EXECUTOR=LocalExecutor
- AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://...
- AIRFLOW__CORE__FERNET_KEY=...
- AIRFLOW__CORE__LOAD_EXAMPLES=False
- AIRFLOW__CORE__DEFAULT_TIMEZONE=Asia/Ho_Chi_Minh

# ✨ NEW (recommended to add):
- AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False        # Security
- AIRFLOW__WEBSERVER__EXPOSE_HOSTNAME=False      # Security
- AIRFLOW__WEBSERVER__EXPOSE_STACKTRACE=False    # Security
- AIRFLOW__SCHEDULER__USE_JOB_SCHEDULE=True      # Performance
```

### 1.2 Updated Docker Compose Section

Replace current airflow-webserver section với:

```yaml
  airflow-webserver:
    build:
      context: ./airflow
      dockerfile: Dockerfile
    container_name: airflow-webserver
    hostname: airflow-webserver
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Core configuration
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - AIRFLOW__CORE__FERNET_KEY=46BKJoQYlPPOexq0OhDZnIlNepKFf87WFwLbfzqDDho=
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
      - AIRFLOW__CORE__DEFAULT_TIMEZONE=Asia/Ho_Chi_Minh
      
      # Connections (unchanged)
      - AIRFLOW_CONN_SPARK_DEFAULT=spark://spark-master:7077
      - AIRFLOW_CONN_AWS_DEFAULT=aws://minioadmin:minioadmin@?host=http://minio:9000&region_name=us-east-1
      
      # Security settings (Airflow 3.x enhanced)
      - AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False
      - AIRFLOW__WEBSERVER__EXPOSE_HOSTNAME=False
      - AIRFLOW__WEBSERVER__EXPOSE_STACKTRACE=False
      
      # Performance tuning (Airflow 3.x)
      - AIRFLOW__CORE__PARALLELISM=32
      - AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=16
      
      # Auto-initialization (unchanged)
      - _AIRFLOW_DB_UPGRADE=true
      - _AIRFLOW_WWW_USER_CREATE=true
      - _AIRFLOW_WWW_USER_USERNAME=admin
      - _AIRFLOW_WWW_USER_PASSWORD=admin
    ports:
      - "8080:8080"
    volumes:
      - ./dags:/opt/airflow/dags
      - ./spark-jobs:/opt/spark-jobs:ro
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
    networks:
      - lakehouse-network
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s  # Increased from 60s (3.x needs more time)
    command: webserver
    restart: unless-stopped
```

═══════════════════════════════════════════════════════════════════

## 🐍 PART 2: DAG CODE CHANGES

═══════════════════════════════════════════════════════════════════

### 2.1 Removed Operators (Breaking Changes)

```python
# ❌ REMOVED - Will cause ImportError:
from airflow.operators.subdag import SubDagOperator  
from airflow.operators.python import PythonVirtualenvOperator  # Old API

# ✅ REPLACEMENTS:
from airflow.utils.task_group import TaskGroup  # Instead of SubDag
from airflow.decorators import task  # Use @task.virtualenv decorator
```

**Migration Example**:

```python
# BEFORE (Airflow 2.x) - Using SubDagOperator:
from airflow.operators.subdag import SubDagOperator

subdag_task = SubDagOperator(
    task_id='subdag_task',
    subdag=create_subdag(...),
    dag=dag
)

# AFTER (Airflow 3.x) - Using TaskGroup:
from airflow.utils.task_group import TaskGroup

with TaskGroup(group_id='task_group') as tg:
    task1 = BashOperator(...)
    task2 = PythonOperator(...)
    task1 >> task2
```

### 2.2 Execution Date → Logical Date

```python
# ❌ DEPRECATED (still works but warning):
execution_date = context['execution_date']

# ✅ NEW API:
logical_date = context['logical_date']

# Or use data_interval_start / data_interval_end:
data_interval_start = context['data_interval_start']
data_interval_end = context['data_interval_end']
```

**Why this change?**
- "Execution date" was confusing (it's not actually when task executes!)
- "Logical date" better represents the data being processed
- Clearer separation between schedule time vs execution time

### 2.3 DAG Definition Best Practices

```python
# ❌ OLD STYLE (2.x):
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
}

dag = DAG(
    'my_dag',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False
)

# ✅ NEW STYLE (3.x - recommended):
from airflow.models.dag import DAG

dag = DAG(
    dag_id='my_dag',
    schedule='@daily',  # 'schedule' instead of 'schedule_interval'
    catchup=False,
    # Pass args directly (cleaner)
    owner='airflow',
    depends_on_past=False,
    email_on_failure=False,
    retries=1,
    tags=['production', 'batch'],  # Better organization
)
```

**Note**: `schedule_interval` still works, but `schedule` is preferred.

### 2.4 XCom Pull/Push Changes

```python
# ❌ OLD (loose typing):
value = task_instance.xcom_pull(task_ids='upstream_task')

# ✅ NEW (stricter typing - recommended):
from typing import Any

value: Any = task_instance.xcom_pull(
    task_ids='upstream_task',
    key='return_value'  # Explicit key
)
```

### 2.5 TaskFlow API (Enhanced in 3.x)

```python
# TaskFlow API is STRONGLY RECOMMENDED in Airflow 3.x
from airflow.decorators import dag, task
from datetime import datetime

@dag(
    schedule='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['etl', 'taskflow'],
)
def my_etl_dag():
    
    @task
    def extract():
        """Extract data from source"""
        return {'records': 1000}
    
    @task
    def transform(data: dict):
        """Transform data"""
        data['processed'] = True
        return data
    
    @task
    def load(data: dict):
        """Load to destination"""
        print(f"Loading {data['records']} records")
    
    # Define dependencies với >>
    data = extract()
    transformed = transform(data)
    load(transformed)

# Instantiate DAG
my_etl_dag()
```

**Why TaskFlow?**
- Type hints work better
- Automatic XCom handling
- Cleaner code
- Better IDE support

═══════════════════════════════════════════════════════════════════

## 📦 PART 3: PROVIDER PACKAGE VERSIONS

═══════════════════════════════════════════════════════════════════

### 3.1 Version Compatibility Matrix

```
Provider Package Versions for Airflow 3.1.5:
═══════════════════════════════════════════════════════════════

apache-airflow-providers-apache-spark:
├─ Airflow 2.x: 4.6.0
└─ Airflow 3.x: 4.10.1 ← Updated

apache-airflow-providers-amazon:
├─ Airflow 2.x: 8.16.0
└─ Airflow 3.x: 10.2.0 ← Major version bump!

apache-airflow-providers-http:
├─ Airflow 2.x: 4.7.0
└─ Airflow 3.x: 5.1.0

apache-airflow-providers-postgres:
├─ Airflow 2.x: 5.9.0
└─ Airflow 3.x: 6.1.0
```

**IMPORTANT**: Provider versions ≥10.x ONLY work with Airflow 3.x!

### 3.2 Install Commands

```bash
# For Airflow 3.1.5:
pip install apache-airflow-providers-apache-spark==4.10.1
pip install apache-airflow-providers-amazon==10.2.0
pip install apache-airflow-providers-http==5.1.0

# Compatibility check:
airflow providers list  # Shows installed providers
```

═══════════════════════════════════════════════════════════════════

## 🎯 PART 4: NEW FEATURES TO LEVERAGE

═══════════════════════════════════════════════════════════════════

### 4.1 Dataset v2 - Data-Driven Scheduling

```python
from airflow.datasets import Dataset
from airflow.decorators import dag, task
from datetime import datetime

# Define datasets
user_events = Dataset("s3://lakehouse/user-events/")
recommendations = Dataset("s3://lakehouse/recommendations/")

@dag(
    schedule=[user_events],  # Trigger when user_events updated!
    start_date=datetime(2025, 1, 1),
    catchup=False,
)
def compute_recommendations():
    
    @task(outlets=[recommendations])  # Marks dataset as updated
    def generate_recs():
        # ... compute recommendations
        return "Done"
    
    generate_recs()

compute_recommendations()
```

**Why use Datasets?**
- Trigger DAGs based on data availability (not just time)
- Better dependency tracking
- Automatic lineage visualization in UI

### 4.2 Dynamic Task Mapping (Improved)

```python
from airflow.decorators import dag, task

@dag(schedule='@daily', start_date=datetime(2025, 1, 1))
def process_movies():
    
    @task
    def get_movie_ids():
        return ['m001', 'm002', 'm003', 'm004', 'm005']
    
    @task
    def process_movie(movie_id: str):
        print(f"Processing {movie_id}")
        return f"{movie_id}_processed"
    
    # Map over list - creates N tasks dynamically!
    movie_ids = get_movie_ids()
    process_movie.expand(movie_id=movie_ids)

process_movies()
```

**Result**: Creates 5 parallel tasks automatically!

### 4.3 OpenTelemetry Integration

```python
# Airflow 3.x has built-in OTEL support!

# In airflow.cfg or env vars:
[metrics]
otel_on = True
otel_host = localhost
otel_port = 4318

# Automatically exports:
# - Task duration
# - DAG run metrics
# - Scheduler performance
# - Database query times
```

**Benefits**: Can integrate with Prometheus, Grafana, Jaeger immediately!

═══════════════════════════════════════════════════════════════════

## ⚠️ PART 5: GOTCHAS & TROUBLESHOOTING

═══════════════════════════════════════════════════════════════════

### 5.1 Common Errors After Upgrade

**Error 1**: `ImportError: cannot import name 'SubDagOperator'`
```
Solution: Replace with TaskGroup
See section 2.1 above
```

**Error 2**: `Provider version mismatch`
```
Error message:
"Provider apache-airflow-providers-amazon version 8.16.0 
 is not compatible with Airflow 3.x"

Solution:
pip install --upgrade apache-airflow-providers-amazon==10.2.0
```

**Error 3**: `Database migration failed`
```
Error: Alembic migration error

Solution:
1. Backup database first!
2. Run: airflow db migrate
3. If fails, check compatibility:
   airflow db check-migrations
```

**Error 4**: `RBAC configuration deprecated`
```
Warning: AIRFLOW__WEBSERVER__RBAC is deprecated

Solution:
Remove from docker-compose.yaml
(RBAC is always enabled in 3.x)
```

### 5.2 Performance Tuning for 3.x

```yaml
# Recommended settings for Airflow 3.x:
environment:
  # Scheduler optimization
  - AIRFLOW__SCHEDULER__USE_JOB_SCHEDULE=True
  - AIRFLOW__SCHEDULER__MAX_TIS_PER_QUERY=512
  - AIRFLOW__SCHEDULER__PARSING_PROCESSES=2
  
  # Database connection pool
  - AIRFLOW__DATABASE__SQL_ALCHEMY_POOL_SIZE=10
  - AIRFLOW__DATABASE__SQL_ALCHEMY_MAX_OVERFLOW=20
  
  # Task execution
  - AIRFLOW__CORE__PARALLELISM=32
  - AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=16
  - AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=16
```

═══════════════════════════════════════════════════════════════════

## 📝 PART 6: MIGRATION CHECKLIST

═══════════════════════════════════════════════════════════════════

### Phase 1: Pre-Migration (Testing)
```
☐ Backup Airflow metadata database
☐ Export current connections: airflow connections export
☐ Export variables: airflow variables export
☐ Test DAGs in Airflow 3.x dev environment
☐ Update provider packages
☐ Check for deprecated operators
```

### Phase 2: Docker Setup
```
☐ Update Dockerfile to use 3.1.5 base image
☐ Update provider package versions in requirements
☐ Update docker-compose environment variables
☐ Remove deprecated RBAC settings
☐ Add new security settings
```

### Phase 3: Code Updates
```
☐ Replace SubDagOperator with TaskGroup
☐ Update execution_date → logical_date
☐ Update schedule_interval → schedule
☐ Add type hints to TaskFlow tasks
☐ Test all custom operators/sensors
```

### Phase 4: Deployment
```
☐ Stop Airflow 2.x containers
☐ Run database migration: airflow db migrate
☐ Start Airflow 3.x containers
☐ Import connections & variables
☐ Verify DAGs parse correctly
☐ Run test DAG executions
☐ Monitor logs for warnings
```

### Phase 5: Post-Migration
```
☐ Enable OpenTelemetry metrics
☐ Update monitoring dashboards
☐ Update documentation
☐ Train team on new UI features
☐ Celebrate! 🎉
```

═══════════════════════════════════════════════════════════════════

## 🚀 QUICK START - Minimal Migration

Nếu anh muốn upgrade NHANH nhất mà minimal risk:

```bash
# Step 1: Update Dockerfile
# (Use the new Dockerfile I created above)

# Step 2: Update only critical env vars in docker-compose:
environment:
  - AIRFLOW__WEBSERVER__EXPOSE_CONFIG=False
  - AIRFLOW__SCHEDULER__USE_JOB_SCHEDULE=True
  
# Remove this line:
# - AIRFLOW__WEBSERVER__RBAC=True

# Step 3: Rebuild and start:
docker compose -f docker-compose.unified.yaml build airflow-webserver airflow-scheduler
docker compose -f docker-compose.unified.yaml up -d

# Step 4: Check logs:
docker logs -f airflow-webserver
docker logs -f airflow-scheduler

# Step 5: Access UI:
http://localhost:8080
```

**Expected outcome**: Airflow 3.x running, most 2.x DAGs work unchanged!

═══════════════════════════════════════════════════════════════════

## 📚 RESOURCES

- Official Migration Guide: https://airflow.apache.org/docs/apache-airflow/3.1.5/migrations/
- Provider Compatibility: https://airflow.apache.org/docs/apache-airflow-providers/
- Release Notes: https://airflow.apache.org/docs/apache-airflow/3.1.5/release_notes.html
- Slack Community: https://apache-airflow.slack.com/

═══════════════════════════════════════════════════════════════════

Anh Long ơi, đó là toàn bộ migration guide! 

**Key takeaway**: Airflow 3.x is MUCH better than 2.x và migration không khó lắm. 
Đa số code có thể giữ nguyên, chỉ cần:
1. Update Docker base image
2. Fix a few env vars
3. Replace SubDagOperator nếu có dùng
4. Update provider versions

Anh muốn tôi giải thích thêm phần nào không? 🚀