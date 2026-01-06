import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from asyncpg import Pool

class LogRepository:
    def __init__(self, db: Pool):
        self.db = db

    async def log_recommendation_served(
        self,
        user_id: str,
        session_id: str,
        recommendations: List[Dict],
        algorithm_source: str,
        context: Dict,
        computation_time_ms: int,
        cache_hit: bool
    ) -> int:
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
        rec_log_id = await self.db.fetchval(
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

    async def get_log_entry(self, log_id: int) -> Optional[Dict]:
        query = """
            SELECT recommended_movies, timestamp
            FROM recommendation_logs
            WHERE id = $1
        """
        row = await self.db.fetchrow(query, log_id)
        return dict(row) if row else None

    async def log_feedback(
        self,
        rec_log_id: int,
        movie_id: str,
        position: Optional[int],
        event_type: str,
        rating: Optional[int],
        watch_duration_sec: Optional[int],
        session_id: str,
        time_to_event_sec: int
    ):
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
        await self.db.execute(
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

    async def get_cache_stats(self) -> Dict:
        query_cache = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN cache_hit THEN 1 END) as hits
            FROM recommendation_logs
            WHERE timestamp > NOW() - INTERVAL '1 hour'
        """
        row = await self.db.fetchrow(query_cache)
        return dict(row) if row else {'total': 0, 'hits': 0}

    async def get_ctr_stats(self) -> Dict:
        query_ctr = """
            SELECT 
                COUNT(DISTINCT l.id) as recommendations,
                COUNT(DISTINCT CASE WHEN f.event_type = 'click' THEN l.id END) as clicks
            FROM recommendation_logs l
            LEFT JOIN recommendation_feedback f ON l.id = f.rec_log_id
            WHERE l.timestamp > NOW() - INTERVAL '1 hour'
        """
        row = await self.db.fetchrow(query_ctr)
        return dict(row) if row else {'recommendations': 0, 'clicks': 0}
