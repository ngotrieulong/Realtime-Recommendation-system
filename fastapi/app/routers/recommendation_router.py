from fastapi import APIRouter, Depends, Request
from typing import Optional

from ..schemas.recommendation import RecommendationResponse, MovieListingResponse
from ..dependencies import get_db_pool, get_redis
from ..repositories.movie_repository import MovieRepository
from ..repositories.log_repository import LogRepository
from ..services.recommendation_service import RecommendationService
from ..limiter import limiter

router = APIRouter()

async def get_repository_service(
    db = Depends(get_db_pool),
    redis_client = Depends(get_redis)
) -> RecommendationService:
    movie_repo = MovieRepository(db)
    log_repo = LogRepository(db)
    return RecommendationService(movie_repo, log_repo, redis_client)

@router.get("/api/recommendations", response_model=RecommendationResponse)
@limiter.limit("20/minute")  # Stricter limit for recommendations
async def get_recommendations(
    user_id: str,
    request: Request, # Required for limiter
    limit: int = 20,
    session_id: Optional[str] = None,
    service: RecommendationService = Depends(get_repository_service)
):
    """
    Get personalized movie recommendations
    """
    return await service.get_recommendations(user_id, limit, session_id, request)

@router.get("/api/movies", response_model=MovieListingResponse)
async def get_movies(
    limit: int = 50,
    offset: int = 0,
    genre: Optional[str] = None,
    service: RecommendationService = Depends(get_repository_service)
):
    """
    Browse movie catalog
    """
    return await service.get_movies(limit, offset, genre)
