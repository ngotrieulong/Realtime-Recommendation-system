"""
=============================================================================
ENHANCED FASTAPI - Movie Recommendation System
=============================================================================
Features:
  - Hybrid recommendation blending (L2 realtime + L3 batch)
  - Gradual cache expiration with valid_until
  - Comprehensive logging (recommendation_logs, recommendation_feedback)
  - 3-tier caching strategy
  - Async operations for performance
=============================================================================
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis
import asyncpg
from aiokafka import AIOKafkaProducer
import numpy as np

# =============================================================================
# CONFIGURATION
# =============================================================================
REDIS_URL = "redis://redis:6379"
POSTGRES_DSN = "postgresql://airflow:airflow@postgres:5432/moviedb"
KAFKA_BOOTSTRAP_SERVERS = "kafka:29092"
KAFKA_TOPIC_EVENTS = "movie-events"

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_VALID_UNTIL_BUFFER = 3600  # Additional hour for gradual expiration

# Hybrid blending weights
BATCH_WEIGHT = 0.7  # 70% weight to batch recommendations
REALTIME_WEIGHT = 0.3  # 30% weight to realtime recommendations


# =============================================================================
# PYDANTIC MODELS
# =============================================================================
class UserEvent(BaseModel):
    """User interaction event"""
    user_id: str = Field(..., min_length=1, max_length=100)
    movie_id: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., regex="^(click|view|play|rate|favorite|skip)$")
    rating: Optional[int] = Field(None, ge=1, le=5)
    watch_duration_sec: Optional[int] = Field(None, ge=0)
    session_id: Optional[str] = None
    rec_log_id: Optional[int] = None  # Link to recommendation that triggered this


class MovieRecommendation(BaseModel):
    """Single movie recommendation"""
    movie_id: str
    title: str
    score: float
    source: str  # 'batch', 'realtime', or 'hybrid'


class RecommendationResponse(BaseModel):
    """API response for recommendations"""
    user_id: str
    recommendations: List[MovieRecommendation]
    metadata: Dict[str, Any]


# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(
    title="Movie Recommendation API",
    description="Production-ready recommendation system with Lambda Architecture",
    version="2.0.0"
)

# =============================================================================
# CORS CONFIGURATION - Allow frontend to connect
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React development server
        "http://127.0.0.1:3000",
        # Add production frontend URL here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global connections (initialized on startup)
redis_client: Optional[redis.Redis] = None
pg_pool: Optional[asyncpg.Pool] = None
kafka_producer: Optional[AIOKafkaProducer] = None


# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================
@app.on_event("startup")
async def startup():
    """Initialize connections on startup"""
    global redis_client, pg_pool, kafka_producer
    
    # Redis connection
    redis_client = await redis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    
    # PostgreSQL connection pool
    pg_pool = await asyncpg.create_pool(
        POSTGRES_DSN,
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    
    # Kafka producer
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await kafka_producer.start()
    
    print("✅ All connections initialized")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup connections on shutdown"""
    if redis_client:
        await redis_client.close()
    if pg_pool:
        await pg_pool.close()
    if kafka_producer:
        await kafka_producer.stop()
    
    print("👋 All connections closed")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
async def get_batch_recommendations(user_id: str) -> List[Dict]:
    """Get pre-computed recommendations from L3 (batch layer)"""
    query = """
        SELECT recommendations, model_version, computed_at
        FROM batch_recommendations
        WHERE user_id = $1 AND expires_at > NOW()
    """
    
    row = await pg_pool.fetchrow(query, user_id)
    
    if row:
        recs = json.loads(row['recommendations']) if isinstance(row['recommendations'], str) else row['recommendations']
        return recs
    
    return []


async def compute_realtime_recommendations(user_id: str, limit: int = 50) -> List[Dict]:
    """Compute recommendations from L2 (realtime user profile + pgvector)"""
    
    # Step 1: Get user preference vector
    query_profile = """
        SELECT preference_vector
        FROM user_profiles
        WHERE user_id = $1
    """
    
    profile = await pg_pool.fetchrow(query_profile, user_id)
    
    if not profile or not profile['preference_vector']:
        return []  # No profile yet, will fallback to batch
    
    # Convert pgvector string to list
    user_vector = profile['preference_vector']
    
    # Step 2: Get movies user already interacted with (exclude them)
    query_watched = """
        SELECT DISTINCT movie_id
        FROM rt_user_interactions
        WHERE user_id = $1
    """
    
    watched_movies = await pg_pool.fetch(query_watched, user_id)
    watched_ids = [row['movie_id'] for row in watched_movies]
    
    # Step 3: Find similar movies using pgvector
    query_similar = """
        SELECT 
            movie_id,
            title,
            1 - (embedding <=> $1::vector) AS similarity_score
        FROM movies
        WHERE movie_id != ALL($2::varchar[])
        ORDER BY embedding <=> $1::vector
        LIMIT $3
    """
    
    similar_movies = await pg_pool.fetch(
        query_similar,
        user_vector,
        watched_ids,
        limit
    )
    
    # Format results
    recommendations = [
        {
            "movie_id": row['movie_id'],
            "title": row['title'],
            "score": float(row['similarity_score'])
        }
        for row in similar_movies
    ]
    
    return recommendations


async def blend_recommendations(
    batch_recs: List[Dict],
    realtime_recs: List[Dict],
    limit: int = 20
) -> List[Dict]:
    """
    Hybrid blending: Combine batch (70%) + realtime (30%) recommendations
    
    Algorithm:
    1. Create score dictionary
    2. For each movie in batch: score = batch_score * 0.7
    3. For each movie in realtime: 
       - If already in dict: score += realtime_score * 0.3 (double boost!)
       - Else: score = realtime_score * 0.3
    4. Sort by final score
    """
    scores = {}
    
    # Add batch recommendations (70% weight)
    for rec in batch_recs:
        movie_id = rec['movie_id']
        scores[movie_id] = {
            'movie_id': movie_id,
            'title': rec.get('title', ''),
            'score': rec['score'] * BATCH_WEIGHT,
            'batch_score': rec['score'],
            'realtime_score': 0.0
        }
    
    # Add/boost with realtime recommendations (30% weight)
    for rec in realtime_recs:
        movie_id = rec['movie_id']
        
        if movie_id in scores:
            # Movie in BOTH lists → double boost!
            scores[movie_id]['score'] += rec['score'] * REALTIME_WEIGHT
            scores[movie_id]['realtime_score'] = rec['score']
        else:
            # New movie from realtime only
            scores[movie_id] = {
                'movie_id': movie_id,
                'title': rec.get('title', ''),
                'score': rec['score'] * REALTIME_WEIGHT,
                'batch_score': 0.0,
                'realtime_score': rec['score']
            }
    
    # Sort by final score and take top N
    sorted_recs = sorted(
        scores.values(),
        key=lambda x: x['score'],
        reverse=True
    )[:limit]
    
    return sorted_recs


async def log_recommendation_served(
    user_id: str,
    session_id: str,
    recommendations: List[Dict],
    algorithm_source: str,
    computation_time_ms: int,
    cache_hit: bool,
    request: Request
) -> int:
    """
    Log recommendation serving event to recommendation_logs table
    Returns: rec_log_id for linking feedback
    """
    
    context = {
        "device": request.headers.get("user-agent", "unknown"),
        "page": request.query_params.get("page", "homepage"),
        # Could add A/B test group here
    }
    
    query = """
        INSERT INTO recommendation_logs (
            user_id,
            session_id,
            recommended_movies,
            algorithm_source,
            context,
            total_candidates,
            computation_time_ms,
            cache_hit,
            timestamp
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        RETURNING id
    """
    
    rec_log_id = await pg_pool.fetchval(
        query,
        user_id,
        session_id,
        json.dumps(recommendations),
        algorithm_source,
        json.dumps(context),
        len(recommendations),
        computation_time_ms,
        cache_hit
    )
    
    return rec_log_id


async def log_recommendation_feedback(
    rec_log_id: int,
    movie_id: str,
    event_type: str,
    rating: Optional[int],
    watch_duration_sec: Optional[int],
    session_id: str,
    recommendation_timestamp: datetime
):
    """Log user feedback on a specific recommendation"""
    
    # Calculate time from recommendation to event
    time_to_event_sec = int((datetime.now() - recommendation_timestamp).total_seconds())
    
    # Find position in original recommendation list
    query_position = """
        SELECT 
            recommended_movies,
            timestamp
        FROM recommendation_logs
        WHERE id = $1
    """
    
    rec_log = await pg_pool.fetchrow(query_position, rec_log_id)
    
    if rec_log:
        recs = json.loads(rec_log['recommended_movies']) if isinstance(rec_log['recommended_movies'], str) else rec_log['recommended_movies']
        
        # Find position (1-based)
        position = next(
            (i + 1 for i, r in enumerate(recs) if r['movie_id'] == movie_id),
            None
        )
        
        # Insert feedback
        query_insert = """
            INSERT INTO recommendation_feedback (
                rec_log_id,
                movie_id,
                position_in_list,
                event_type,
                rating,
                watch_duration_sec,
                timestamp,
                time_to_event_sec,
                session_id
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8)
        """
        
        await pg_pool.execute(
            query_insert,
            rec_log_id,
            movie_id,
            position,
            event_type,
            rating,
            watch_duration_sec,
            time_to_event_sec,
            session_id
        )


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: str,
    limit: int = 20,
    session_id: Optional[str] = None,
    request: Request = None
):
    """
    Get personalized movie recommendations
    
    Strategy:
    1. Check L1 (Redis cache) with validity check
    2. If miss/expired, compute hybrid (L2 + L3)
    3. Cache result with valid_until
    4. Log serving event
    """
    start_time = time.time()
    
    # Generate session ID if not provided
    if not session_id:
        session_id = f"session_{uuid.uuid4()}"
    
    # =========================================================================
    # STEP 1: Check L1 (Redis Cache)
    # =========================================================================
    cache_key = f"recs:{user_id}"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        cached = json.loads(cached_data)
        
        # Check validity (gradual expiration)
        valid_until = datetime.fromisoformat(cached['valid_until'])
        
        if datetime.now() < valid_until:
            # Cache still valid
            computation_time = int((time.time() - start_time) * 1000)
            
            # Still log the serve (for analytics)
            rec_log_id = await log_recommendation_served(
                user_id=user_id,
                session_id=session_id,
                recommendations=cached['recommendations'],
                algorithm_source=cached['source'],
                computation_time_ms=computation_time,
                cache_hit=True,
                request=request
            )
            
            return RecommendationResponse(
                user_id=user_id,
                recommendations=[
                    MovieRecommendation(**rec) for rec in cached['recommendations']
                ],
                metadata={
                    "source": cached['source'],
                    "cached": True,
                    "computation_time_ms": computation_time,
                    "rec_log_id": rec_log_id,
                    "model_version": cached.get('model_version', 'unknown')
                }
            )
    
    # =========================================================================
    # STEP 2: Cache Miss - Compute Hybrid Recommendations
    # =========================================================================
    
    # Get both batch and realtime recommendations
    batch_recs = await get_batch_recommendations(user_id)
    realtime_recs = await compute_realtime_recommendations(user_id, limit=50)
    
    # Determine source and blend if both available
    if batch_recs and realtime_recs:
        # HYBRID: Blend both
        recommendations = await blend_recommendations(batch_recs, realtime_recs, limit)
        algorithm_source = "hybrid"
        model_version = "hybrid_batch+realtime"
        
    elif realtime_recs:
        # Realtime only (no batch available)
        recommendations = realtime_recs[:limit]
        for rec in recommendations:
            rec['source'] = 'realtime'
        algorithm_source = "realtime"
        model_version = "realtime_pgvector"
        
    elif batch_recs:
        # Batch only (no realtime profile)
        recommendations = batch_recs[:limit]
        for rec in recommendations:
            rec['source'] = 'batch'
        algorithm_source = "batch"
        
        # Get model version from batch_recommendations
        query_version = """
            SELECT model_version FROM batch_recommendations WHERE user_id = $1
        """
        row = await pg_pool.fetchrow(query_version, user_id)
        model_version = row['model_version'] if row else 'unknown'
        
    else:
        # Fallback: Popular movies (cold start)
        query_popular = """
            SELECT movie_id, title, avg_rating as score
            FROM movies
            ORDER BY total_ratings DESC, avg_rating DESC
            LIMIT $1
        """
        popular = await pg_pool.fetch(query_popular, limit)
        recommendations = [
            {
                "movie_id": row['movie_id'],
                "title": row['title'],
                "score": float(row['score']),
                "source": "popular"
            }
            for row in popular
        ]
        algorithm_source = "popular"
        model_version = "fallback_popular"
    
    # =========================================================================
    # STEP 3: Cache Result with valid_until
    # =========================================================================
    computation_time = int((time.time() - start_time) * 1000)
    
    # Set valid_until to align with next batch job (3 AM)
    now = datetime.now()
    next_batch_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now.hour >= 3:
        next_batch_time += timedelta(days=1)
    
    cache_value = {
        "recommendations": recommendations,
        "source": algorithm_source,
        "model_version": model_version,
        "generated_at": now.isoformat(),
        "valid_until": next_batch_time.isoformat()
    }
    
    await redis_client.setex(
        cache_key,
        CACHE_TTL_SECONDS,
        json.dumps(cache_value)
    )
    
    # =========================================================================
    # STEP 4: Log Serving Event
    # =========================================================================
    rec_log_id = await log_recommendation_served(
        user_id=user_id,
        session_id=session_id,
        recommendations=recommendations,
        algorithm_source=algorithm_source,
        computation_time_ms=computation_time,
        cache_hit=False,
        request=request
    )
    
    # =========================================================================
    # STEP 5: Return Response
    # =========================================================================
    return RecommendationResponse(
        user_id=user_id,
        recommendations=[
            MovieRecommendation(
                movie_id=rec['movie_id'],
                title=rec.get('title', ''),
                score=rec['score'],
                source=rec.get('source', algorithm_source)
            )
            for rec in recommendations
        ],
        metadata={
            "source": algorithm_source,
            "cached": False,
            "computation_time_ms": computation_time,
            "rec_log_id": rec_log_id,
            "model_version": model_version,
            "batch_count": len(batch_recs),
            "realtime_count": len(realtime_recs)
        }
    )


@app.post("/api/events")
async def track_event(event: UserEvent):
    """
    Track user interaction event
    
    Flow:
    1. Publish to Kafka (for real-time processing)
    2. Log to recommendation_feedback (if rec_log_id provided)
    3. Return immediately (async)
    """
    
    # Enrich event with server metadata
    enriched_event = {
        **event.dict(),
        "timestamp": datetime.now().isoformat(),
        "server_timestamp": time.time()
    }
    
    # =========================================================================
    # STEP 1: Publish to Kafka (for Spark Streaming)
    # =========================================================================
    try:
        await kafka_producer.send(
            KAFKA_TOPIC_EVENTS,
            value=enriched_event,
            key=event.user_id.encode('utf-8')  # Partition by user_id
        )
    except Exception as e:
        # Log error but don't fail request (graceful degradation)
        print(f"⚠️  Kafka publish failed: {e}")
    
    # =========================================================================
    # STEP 2: Log Feedback (if this event is response to recommendation)
    # =========================================================================
    if event.rec_log_id:
        try:
            # Get recommendation timestamp
            query_rec_time = """
                SELECT timestamp FROM recommendation_logs WHERE id = $1
            """
            rec_row = await pg_pool.fetchrow(query_rec_time, event.rec_log_id)
            
            if rec_row:
                await log_recommendation_feedback(
                    rec_log_id=event.rec_log_id,
                    movie_id=event.movie_id,
                    event_type=event.event_type,
                    rating=event.rating,
                    watch_duration_sec=event.watch_duration_sec,
                    session_id=event.session_id or "unknown",
                    recommendation_timestamp=rec_row['timestamp']
                )
        except Exception as e:
            print(f"⚠️  Feedback logging failed: {e}")
    
    # =========================================================================
    # STEP 3: Return Success (non-blocking)
    # =========================================================================
    return {
        "status": "accepted",
        "message": "Event tracked successfully",
        "event_id": str(uuid.uuid4())
    }


@app.get("/api/movies")
async def get_movies(
    limit: int = 50,
    offset: int = 0,
    genre: Optional[str] = None
):
    """
    Browse movie catalog
    
    Args:
        limit: Number of movies to return
        offset: Pagination offset
        genre: Filter by genre (optional)
    """
    
    # Build query
    if genre:
        query = """
            SELECT movie_id, title, description, genres, release_year, 
                   director, avg_rating, total_ratings
            FROM movies
            WHERE genres @> $1::jsonb
            ORDER BY total_ratings DESC, avg_rating DESC
            LIMIT $2 OFFSET $3
        """
        movies = await pg_pool.fetch(query, f'["{genre}"]', limit, offset)
    else:
        query = """
            SELECT movie_id, title, description, genres, release_year,
                   director, avg_rating, total_ratings
            FROM movies
            ORDER BY total_ratings DESC, avg_rating DESC
            LIMIT $1 OFFSET $2
        """
        movies = await pg_pool.fetch(query, limit, offset)
    
    # Format results
    results = [
        {
            "movie_id": row['movie_id'],
            "title": row['title'],
            "description": row['description'],
            "genres": json.loads(row['genres']) if isinstance(row['genres'], str) else row['genres'],
            "release_year": row['release_year'],
            "director": row['director'],
            "avg_rating": float(row['avg_rating']) if row['avg_rating'] else 0.0,
            "total_ratings": row['total_ratings']
        }
        for row in movies
    ]
    
    return {
        "movies": results,
        "count": len(results),
        "limit": limit,
        "offset": offset
    }


@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics (for monitoring)"""
    
    # Cache hit rate (last hour)
    query_cache = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN cache_hit THEN 1 END) as hits
        FROM recommendation_logs
        WHERE timestamp > NOW() - INTERVAL '1 hour'
    """
    cache_stats = await pg_pool.fetchrow(query_cache)
    
    # CTR (last hour)
    query_ctr = """
        SELECT 
            COUNT(DISTINCT l.id) as recommendations,
            COUNT(DISTINCT CASE WHEN f.event_type = 'click' THEN l.id END) as clicks
        FROM recommendation_logs l
        LEFT JOIN recommendation_feedback f ON l.id = f.rec_log_id
        WHERE l.timestamp > NOW() - INTERVAL '1 hour'
    """
    ctr_stats = await pg_pool.fetchrow(query_ctr)
    
    cache_hit_rate = (cache_stats['hits'] / cache_stats['total'] * 100) if cache_stats['total'] > 0 else 0
    ctr = (ctr_stats['clicks'] / ctr_stats['recommendations'] * 100) if ctr_stats['recommendations'] > 0 else 0
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cache": {
            "total_requests": cache_stats['total'],
            "cache_hits": cache_stats['hits'],
            "hit_rate_percent": round(cache_hit_rate, 2)
        },
        "recommendations": {
            "total_served": ctr_stats['recommendations'],
            "total_clicks": ctr_stats['clicks'],
            "ctr_percent": round(ctr, 2)
        }
    }


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)