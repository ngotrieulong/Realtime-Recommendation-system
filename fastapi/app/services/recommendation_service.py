import json
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import redis.asyncio as redis
from fastapi import Request

from ..repositories.movie_repository import MovieRepository
from ..repositories.log_repository import LogRepository
from ..config import CACHE_TTL_SECONDS, BATCH_WEIGHT, REALTIME_WEIGHT

class RecommendationService:
    def __init__(self, movie_repo: MovieRepository, log_repo: LogRepository, redis_client: redis.Redis):
        self.movie_repo = movie_repo
        self.log_repo = log_repo
        self.redis_client = redis_client

    async def get_recommendations(
        self,
        user_id: str,
        limit: int,
        session_id: str,
        request: Request
    ) -> Dict[str, Any]:
        """
        Get personalized movie recommendations
        Strategy:
        1. Check L1 (Redis cache) with validity check
        2. If miss/expired, compute hybrid (L2 + L3)
        3. Cache result with valid_until
        4. Log serving event
        """
        start_time = time.time()
        if not session_id:
            session_id = f"session_{uuid.uuid4()}"

        # 1. Check L1 Cache
        cache_key = f"recs:{user_id}"
        cached_data = await self.redis_client.get(cache_key)
        
        if cached_data:
            cached = json.loads(cached_data)
            valid_until = datetime.fromisoformat(cached['valid_until'])
            
            if datetime.now() < valid_until:
                computation_time = int((time.time() - start_time) * 1000)
                rec_log_id = await self.log_repo.log_recommendation_served(
                    user_id=user_id,
                    session_id=session_id,
                    recommendations=cached['recommendations'],
                    algorithm_source=cached['source'],
                    context={"device": request.headers.get("user-agent", "unknown"), "page": request.query_params.get("page", "homepage")},
                    computation_time_ms=computation_time,
                    cache_hit=True
                )
                return {
                    "user_id": user_id,
                    "recommendations": cached['recommendations'],
                    "metadata": {
                        "source": cached['source'],
                        "cached": True,
                        "computation_time_ms": computation_time,
                        "rec_log_id": rec_log_id,
                        "model_version": cached.get('model_version', 'unknown')
                    }
                }

        # 2. Cache Miss - Compute Hybrid
        batch_recs = await self.movie_repo.get_batch_recommendations(user_id)
        realtime_recs = await self._compute_realtime_recommendations(user_id, limit=50) # fetch more for blending

        if batch_recs and realtime_recs:
            recommendations = self._blend_recommendations(batch_recs, realtime_recs, limit)
            algorithm_source = "hybrid"
            model_version = "hybrid_batch+realtime"
        elif realtime_recs:
            recommendations = realtime_recs[:limit]
            for rec in recommendations:
                rec['source'] = 'realtime'
            algorithm_source = "realtime"
            model_version = "realtime_pgvector"
        elif batch_recs:
            recommendations = batch_recs[:limit]
            for rec in recommendations:
                rec['source'] = 'batch'
            algorithm_source = "batch"
            meta = await self.movie_repo.get_batch_metadata(user_id)
            model_version = meta['model_version'] if meta else 'unknown'
        else:
            popular = await self.movie_repo.get_popular_movies(limit)
            recommendations = []
            for row in popular:
                recommendations.append({
                    "movie_id": row['movie_id'],
                    "title": row['title'],
                    "poster_url": row.get('poster_url'),
                    "score": float(row['score']),
                    "source": "popular"
                })
            algorithm_source = "popular"
            model_version = "fallback_popular"

        # 3. Cache Result
        computation_time = int((time.time() - start_time) * 1000)
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
        await self.redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(cache_value))

        # 4. Log Serving
        rec_log_id = await self.log_repo.log_recommendation_served(
            user_id=user_id,
            session_id=session_id,
            recommendations=recommendations,
            algorithm_source=algorithm_source,
            context={"device": request.headers.get("user-agent", "unknown"), "page": request.query_params.get("page", "homepage")},
            computation_time_ms=computation_time,
            cache_hit=False
        )

        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "metadata": {
                "source": algorithm_source,
                "cached": False,
                "computation_time_ms": computation_time,
                "rec_log_id": rec_log_id,
                "model_version": model_version
            }
        }

    async def _compute_realtime_recommendations(self, user_id: str, limit: int) -> List[Dict]:
        user_vector = await self.movie_repo.get_user_profile(user_id)
        if not user_vector:
            return []
        
        watched_ids = await self.movie_repo.get_watched_movies(user_id)
        similar_movies = await self.movie_repo.find_similar_movies(user_vector, watched_ids, limit)
        
        return [
            {
                "movie_id": m['movie_id'],
                "title": m['title'],
                "poster_url": m['poster_url'],
                "score": float(m['similarity_score'])
            }
            for m in similar_movies
        ]

    def _blend_recommendations(self, batch_recs: List[Dict], realtime_recs: List[Dict], limit: int) -> List[Dict]:
        scores = {}
        for rec in batch_recs:
            movie_id = rec['movie_id']
            scores[movie_id] = {
                'movie_id': movie_id,
                'title': rec.get('title', ''),
                'poster_url': rec.get('poster_url'),
                'score': rec['score'] * BATCH_WEIGHT,
                'source': 'hybrid'
            }
        
        for rec in realtime_recs:
            movie_id = rec['movie_id']
            if movie_id in scores:
                scores[movie_id]['score'] += rec['score'] * REALTIME_WEIGHT
            else:
                scores[movie_id] = {
                    'movie_id': movie_id,
                    'title': rec.get('title', ''),
                    'poster_url': rec.get('poster_url'),
                    'score': rec['score'] * REALTIME_WEIGHT,
                    'source': 'hybrid'
                }
        
        sorted_recs = sorted(scores.values(), key=lambda x: x['score'], reverse=True)[:limit]
        return sorted_recs

    async def get_movies(self, limit: int, offset: int, genre: Optional[str]) -> Dict[str, Any]:
        movies = await self.movie_repo.get_movies_paginated(limit, offset, genre)
        formatted = [
            {
                "movie_id": m['movie_id'],
                "title": m['title'],
                "description": m['description'],
                "poster_url": m['poster_url'],
                "genres": json.loads(m['genres']) if isinstance(m['genres'], str) else m['genres'],
                "release_year": m['release_year'],
                "director": m['director'],
                "avg_rating": float(m['avg_rating']) if m['avg_rating'] else 0.0,
                "total_ratings": m['total_ratings']
            }
            for m in movies
        ]
        return {
            "movies": formatted,
            "count": len(formatted),
            "limit": limit,
            "offset": offset
        }
