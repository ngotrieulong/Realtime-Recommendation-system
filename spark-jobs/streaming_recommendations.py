"""
=============================================================================
SPARK STRUCTURED STREAMING JOB - REAL-TIME RECOMMENDATION ENGINE
=============================================================================
Architecture Overview:
    Kafka Topic → Spark Streaming → Processing → Postgres + Redis + MinIO

Data Flow:
    1. Read events from Kafka topic 'movie-events'
    2. Parse and validate JSON events
    3. Enrich with movie metadata from Postgres
    4. Update user preference vectors
    5. Compute top-N recommendations via vector similarity
    6. Cache results to Redis for ultra-fast serving
    7. Write raw events to MinIO for batch layer

Performance Target:
    - End-to-end latency: < 500ms (from Kafka to Redis)
    - Throughput: 10,000 events/second
    - P99 latency: < 1 second
=============================================================================
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, udf, current_timestamp, window, 
    count, avg, sum, explode, array, struct, to_json
)
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    TimestampType, DoubleType, ArrayType
)
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import numpy as np


# =============================================================================
# CONFIGURATION
# =============================================================================
# These should be loaded from environment variables in production
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC = "movie-events"
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "moviedb")
POSTGRES_USER = os.getenv("POSTGRES_USER", "airflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "airflow")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

# Streaming parameters
MICRO_BATCH_INTERVAL = "5 seconds"  # Process events every 5 seconds
CHECKPOINT_LOCATION = "s3a://lakehouse/checkpoints/streaming-recs"
OUTPUT_PATH = "s3a://lakehouse/raw-events"


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================
# Define schema for incoming Kafka events
# Why explicit schema? Performance! Spark doesn't need to infer schema from data
event_schema = StructType([
    StructField("event_id", StringType(), False),
    StructField("user_id", StringType(), False),
    StructField("movie_id", StringType(), False),
    StructField("event_type", StringType(), False),  # 'click', 'view', 'rate', 'favorite'
    StructField("rating", IntegerType(), True),       # Only for event_type='rate'
    StructField("session_id", StringType(), True),
    StructField("timestamp", TimestampType(), False)
])


# =============================================================================
# DATABASE HELPER CLASSES
# =============================================================================
class PostgresConnector:
    """
    Singleton connection pool to Postgres
    Why singleton? Avoid creating new connections for each micro-batch
    """
    _connection = None
    
    @classmethod
    def get_connection(cls):
        if cls._connection is None or cls._connection.closed:
            cls._connection = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                cursor_factory=RealDictCursor
            )
        return cls._connection
    
    @classmethod
    def execute_query(cls, query: str, params: tuple = None) -> List[Dict]:
        """Execute SELECT query and return results as list of dicts"""
        conn = cls.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    @classmethod
    def execute_update(cls, query: str, params: tuple = None):
        """Execute INSERT/UPDATE/DELETE query"""
        conn = cls.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            conn.commit()


class RedisConnector:
    """
    Redis client for caching recommendations
    """
    _client = None
    
    @classmethod
    def get_client(cls):
        if cls._client is None:
            cls._client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=0,
                decode_responses=True  # Return strings instead of bytes
            )
        return cls._client
    
    @classmethod
    def cache_recommendations(cls, user_id: str, recommendations: List[Dict], ttl: int = 3600):
        """
        Cache user recommendations with TTL
        
        Args:
            user_id: User identifier
            recommendations: List of {"movie_id": str, "title": str, "score": float}
            ttl: Time-to-live in seconds (default 1 hour)
        """
        client = cls.get_client()
        key = f"recs:{user_id}"
        value = json.dumps(recommendations)
        client.setex(key, ttl, value)


# =============================================================================
# BUSINESS LOGIC FUNCTIONS
# =============================================================================
def get_movie_embedding(movie_id: str) -> np.ndarray:
    """
    Fetch movie embedding vector from Postgres
    
    In production, this would be cached in a distributed cache (e.g., Redis)
    to avoid repeated DB queries. For MVP, we query directly.
    """
    query = """
        SELECT embedding::text 
        FROM movies 
        WHERE movie_id = %s
    """
    result = PostgresConnector.execute_query(query, (movie_id,))
    
    if not result or not result[0]['embedding']:
        return None
    
    # Parse pgvector format: "[0.1, 0.2, ...]" → numpy array
    embedding_str = result[0]['embedding']
    embedding_list = json.loads(embedding_str.replace('[', '[').replace(']', ']'))
    return np.array(embedding_list, dtype=np.float32)


def compute_recommendations(user_id: str, top_n: int = 10) -> List[Dict]:
    """
    Compute personalized recommendations using pgvector similarity search
    
    Algorithm:
        1. Get user's preference vector from user_profiles table
        2. Use pgvector's <=> operator for cosine distance
        3. Exclude movies user has already interacted with
        4. Return top-N similar movies
    
    Returns:
        List of dicts: [{"movie_id": "...", "title": "...", "score": 0.95}, ...]
    """
    # Get user preference vector
    user_query = """
        SELECT preference_vector::text 
        FROM user_profiles 
        WHERE user_id = %s
    """
    user_result = PostgresConnector.execute_query(user_query, (user_id,))
    
    if not user_result or not user_result[0]['preference_vector']:
        # Cold start: return popular movies instead
        return get_popular_movies(top_n)
    
    user_vector_str = user_result[0]['preference_vector']
    
    # Find similar movies using pgvector
    # <=> is cosine distance operator (0 = identical, 2 = opposite)
    # We want movies with LOW distance (high similarity)
    recs_query = f"""
        WITH user_history AS (
            SELECT DISTINCT movie_id 
            FROM rt_user_interactions 
            WHERE user_id = %s 
                AND timestamp > NOW() - INTERVAL '30 days'
        )
        SELECT 
            m.movie_id,
            m.title,
            m.genres,
            1 - (m.embedding <=> %s::vector) as similarity_score
        FROM movies m
        WHERE m.movie_id NOT IN (SELECT movie_id FROM user_history)
            AND m.embedding IS NOT NULL
        ORDER BY m.embedding <=> %s::vector
        LIMIT %s
    """
    
    recommendations = PostgresConnector.execute_query(
        recs_query, 
        (user_id, user_vector_str, user_vector_str, top_n)
    )
    
    # Format for API response
    return [
        {
            "movie_id": rec['movie_id'],
            "title": rec['title'],
            "genres": rec['genres'],
            "score": float(rec['similarity_score'])
        }
        for rec in recommendations
    ]


def get_popular_movies(top_n: int = 10) -> List[Dict]:
    """
    Fallback recommendations for cold-start users
    Returns globally popular movies based on views and ratings
    """
    query = """
        SELECT 
            movie_id,
            title,
            genres,
            (total_views * 0.3 + avg_rating * 10000) as popularity_score
        FROM movies
        WHERE total_views > 1000
        ORDER BY popularity_score DESC
        LIMIT %s
    """
    
    popular = PostgresConnector.execute_query(query, (top_n,))
    
    return [
        {
            "movie_id": movie['movie_id'],
            "title": movie['title'],
            "genres": movie['genres'],
            "score": 1.0  # Placeholder score for popular movies
        }
        for movie in popular
    ]


def update_user_profile(user_id: str, movie_id: str, event_type: str, rating: int = None):
    """
    Incrementally update user preference vector based on interaction
    
    Strategy:
        - For 'view' events: small update (weight=0.05)
        - For 'rate' events: larger update (weight=0.2), scaled by rating
        - For 'favorite' events: strong update (weight=0.3)
    
    Algorithm (Exponential Moving Average):
        new_vector = (1 - α) * old_vector + α * movie_embedding
        where α is the learning rate (weight)
    """
    # Determine update weight based on event type
    weight_map = {
        'click': 0.02,
        'view': 0.05,
        'rate': 0.2,
        'favorite': 0.3
    }
    base_weight = weight_map.get(event_type, 0.05)
    
    # Scale weight by rating if available
    if rating:
        # Rating scale: 1-5 → weight scale: 0.5x - 1.5x
        rating_multiplier = (rating - 3) * 0.25 + 1  # Rating 3 = 1x, 5 = 1.5x, 1 = 0.5x
        weight = base_weight * rating_multiplier
    else:
        weight = base_weight
    
    # Get movie embedding
    movie_embedding = get_movie_embedding(movie_id)
    if movie_embedding is None:
        return  # Skip if movie has no embedding
    
    # Use Postgres function for atomic update
    update_query = """
        SELECT update_user_preference(%s, %s::vector, %s)
    """
    
    embedding_str = '[' + ','.join(map(str, movie_embedding)) + ']'
    PostgresConnector.execute_update(
        update_query,
        (user_id, embedding_str, weight)
    )


def log_interaction_to_postgres(event: Dict):
    """
    Write interaction event to rt_user_interactions table
    This table is used for:
        1. Real-time analytics (recent views, trending movies)
        2. Excluding already-watched movies from recommendations
        3. Source data for batch layer (archived daily)
    """
    insert_query = """
        INSERT INTO rt_user_interactions 
            (user_id, movie_id, interaction_type, rating, session_id, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    PostgresConnector.execute_update(
        insert_query,
        (
            event['user_id'],
            event['movie_id'],
            event['event_type'],
            event.get('rating'),
            event.get('session_id'),
            event['timestamp']
        )
    )


# =============================================================================
# SPARK STREAMING JOB LOGIC
# =============================================================================
def process_micro_batch(batch_df, batch_id):
    """
    Process each micro-batch of events
    
    This function is called by Spark for each micro-batch interval (5 seconds).
    It performs all the business logic: validation, enrichment, user profile updates,
    recommendation computation, and caching.
    
    Args:
        batch_df: Spark DataFrame containing events from current micro-batch
        batch_id: Unique ID for this micro-batch (for debugging/monitoring)
    """
    print(f"🔄 Processing micro-batch {batch_id} with {batch_df.count()} events")
    
    # Convert Spark DataFrame to list of dicts for processing
    # Why not use Spark transformations? Because we need to:
    #   1. Make external calls (Postgres, Redis)
    #   2. Complex business logic not easily expressible in Spark SQL
    events = [row.asDict() for row in batch_df.collect()]
    
    # Group events by user for batch processing
    events_by_user = {}
    for event in events:
        user_id = event['user_id']
        if user_id not in events_by_user:
            events_by_user[user_id] = []
        events_by_user[user_id].append(event)
    
    # Process each user's events
    for user_id, user_events in events_by_user.items():
        try:
            # Step 1: Log all interactions to Postgres
            for event in user_events:
                log_interaction_to_postgres(event)
            
            # Step 2: Update user preference vector incrementally
            for event in user_events:
                update_user_profile(
                    user_id=event['user_id'],
                    movie_id=event['movie_id'],
                    event_type=event['event_type'],
                    rating=event.get('rating')
                )
            
            # Step 3: Compute fresh recommendations
            recommendations = compute_recommendations(user_id, top_n=20)
            
            # Step 4: Cache to Redis for fast API serving
            RedisConnector.cache_recommendations(user_id, recommendations, ttl=3600)
            
            print(f"✅ Updated recommendations for user {user_id}: {len(recommendations)} movies")
            
        except Exception as e:
            print(f"❌ Error processing user {user_id}: {str(e)}")
            # In production, send to dead-letter queue for retry
            continue
    
    print(f"✨ Micro-batch {batch_id} completed successfully")


def main():
    """
    Main entry point for Spark Streaming job
    """
    # ==========================================================================
    # SPARK SESSION INITIALIZATION
    # ==========================================================================
    spark = SparkSession.builder \
        .appName("RealTimeRecommendationEngine") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.shuffle.partitions", "10") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")  # Reduce log verbosity
    
    print("🚀 Starting Real-Time Recommendation Engine")
    print(f"📡 Kafka: {KAFKA_BOOTSTRAP_SERVERS}, Topic: {KAFKA_TOPIC}")
    print(f"💾 Checkpoint: {CHECKPOINT_LOCATION}")
    print(f"⏱️  Micro-batch interval: {MICRO_BATCH_INTERVAL}")
    
    # ==========================================================================
    # KAFKA STREAM READER
    # ==========================================================================
    # Read from Kafka topic as a stream
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .option("maxOffsetsPerTrigger", 10000) \
        .load()
    
    # Parse JSON from Kafka value field
    events_df = kafka_df.selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), event_schema).alias("event")) \
        .select("event.*")
    
    # ==========================================================================
    # DUAL WRITE: Process + Archive
    # ==========================================================================
    # Write 1: Process events for real-time recommendations
    query_processing = events_df \
        .writeStream \
        .foreachBatch(process_micro_batch) \
        .trigger(processingTime=MICRO_BATCH_INTERVAL) \
        .start()
    
    # Write 2: Archive raw events to MinIO (for batch layer)
    # Partition by date for efficient batch processing
    query_archival = events_df \
        .withColumn("date", col("timestamp").cast("date")) \
        .withColumn("hour", col("timestamp").cast("string").substr(12, 2)) \
        .writeStream \
        .format("parquet") \
        .option("path", OUTPUT_PATH) \
        .option("checkpointLocation", f"{CHECKPOINT_LOCATION}/archival") \
        .partitionBy("date", "hour") \
        .trigger(processingTime="1 minute") \
        .start()
    
    # ==========================================================================
    # MONITORING & METRICS
    # ==========================================================================
    # Log progress every 30 seconds
    def log_progress():
        while True:
            import time
            time.sleep(30)
            progress = query_processing.lastProgress
            if progress:
                print(f"""
                📊 Streaming Metrics:
                    Batch ID: {progress['batchId']}
                    Input Rows: {progress['numInputRows']}
                    Processing Rate: {progress.get('processedRowsPerSecond', 0):.2f} rows/sec
                    Latency: {progress.get('durationMs', {}).get('triggerExecution', 0)}ms
                """)
    
    # Start monitoring thread
    import threading
    monitor_thread = threading.Thread(target=log_progress, daemon=True)
    monitor_thread.start()
    
    # ==========================================================================
    # WAIT FOR TERMINATION
    # ==========================================================================
    print("✅ Streaming job started successfully. Processing events...")
    query_processing.awaitTermination()


if __name__ == "__main__":
    main()