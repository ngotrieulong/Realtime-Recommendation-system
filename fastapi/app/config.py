
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://airflow:airflow@postgres:5432/moviedb")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC_EVENTS = os.getenv("KAFKA_TOPIC_EVENTS", "movie-events")

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_VALID_UNTIL_BUFFER = 3600  # Additional hour for gradual expiration

# Hybrid blending weights
BATCH_WEIGHT = 0.7  # 70% weight to batch recommendations
REALTIME_WEIGHT = 0.3  # 30% weight to realtime recommendations
