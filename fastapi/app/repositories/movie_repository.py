import json
from typing import List, Dict, Optional, Any
from asyncpg import Pool

class MovieRepository:
    def __init__(self, db: Pool):
        self.db = db

    async def get_batch_recommendations(self, user_id: str) -> List[Dict]:
        """Get pre-computed recommendations from L3 (batch layer)"""
        query = """
            SELECT recommendations, model_version, computed_at
            FROM batch_recommendations
            WHERE user_id = $1 AND expires_at > NOW()
        """
        row = await self.db.fetchrow(query, user_id)
        if row:
            recs = json.loads(row['recommendations']) if isinstance(row['recommendations'], str) else row['recommendations']
            # Attach metadata if needed, but for now returning list
            # We might want to return model_version too, but the original logic just returned list.
            # I'll augment it slightly to match the 'recs' list expectation or change logic in service. 
            # Original helper returned just the list.
            return recs
        return []
    
    async def get_batch_metadata(self, user_id: str) -> Optional[Dict]:
        """Helper to get metadata for batch recs"""
        query = """
            SELECT model_version, computed_at
            FROM batch_recommendations
            WHERE user_id = $1
        """
        row = await self.db.fetchrow(query, user_id)
        if row:
            return dict(row)
        return None

    async def get_user_profile(self, user_id: str) -> Optional[List[float]]:
        query_profile = """
            SELECT preference_vector
            FROM user_profiles
            WHERE user_id = $1
        """
        row = await self.db.fetchrow(query_profile, user_id)
        if row and row['preference_vector']:
            # Assuming pgvector returns a string or list. asyncpg usually decodes vector if type is set, 
            # simplified original logic: "Convert pgvector string to list" implied it might be string.
            # We'll return it as is, service can handle.
            return row['preference_vector']
        return None

    async def get_watched_movies(self, user_id: str) -> List[str]:
        query_watched = """
            SELECT DISTINCT movie_id
            FROM rt_user_interactions
            WHERE user_id = $1
        """
        rows = await self.db.fetch(query_watched, user_id)
        return [row['movie_id'] for row in rows]

    async def find_similar_movies(self, user_vector: Any, exclude_ids: List[str], limit: int) -> List[Dict]:
        query_similar = """
            SELECT 
                movie_id,
                title,
                poster_url,
                1 - (embedding <=> $1::vector) AS similarity_score
            FROM movies
            WHERE movie_id != ALL($2::varchar[])
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """
        rows = await self.db.fetch(query_similar, user_vector, exclude_ids, limit)
        return [dict(row) for row in rows]

    async def get_popular_movies(self, limit: int) -> List[Dict]:
        query_popular = """
            SELECT movie_id, title, avg_rating as score
            FROM movies
            ORDER BY total_ratings DESC, avg_rating DESC
            LIMIT $1
        """
        rows = await self.db.fetch(query_popular, limit)
        return [dict(row) for row in rows]

    async def get_movies_paginated(self, limit: int, offset: int, genre: Optional[str] = None) -> List[Dict]:
        if genre:
            query = """
                SELECT movie_id, title, description, genres, release_year, 
                       director, poster_url, avg_rating, total_ratings
                FROM movies
                WHERE genres @> $1::jsonb
                ORDER BY total_ratings DESC, avg_rating DESC
                LIMIT $2 OFFSET $3
            """
            rows = await self.db.fetch(query, f'["{genre}"]', limit, offset)
        else:
            query = """
                SELECT movie_id, title, description, genres, release_year,
                       director, poster_url, avg_rating, total_ratings
                FROM movies
                ORDER BY total_ratings DESC, avg_rating DESC
                LIMIT $1 OFFSET $2
            """
            rows = await self.db.fetch(query, limit, offset)
        
        return [dict(row) for row in rows]
