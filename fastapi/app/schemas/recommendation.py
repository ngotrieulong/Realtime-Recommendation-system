from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MovieRecommendationRequest(BaseModel):
    """Input from Frontend/Client"""
    user_id: str = Field(..., min_length=1)
    limit: int = Field(20, ge=1, le=100)

class MovieItem(BaseModel):
    """Single movie in response (simplified)"""
    movie_id: str
    title: str
    score: float
    poster_url: Optional[str] = None

class MovieRecommendation(BaseModel):
    """Single movie recommendation with detailed source info"""
    movie_id: str
    title: str
    poster_url: Optional[str] = None
    score: float
    source: str  # 'batch', 'realtime', or 'hybrid'

class RecommendationResponse(BaseModel):
    """API response for recommendations"""
    user_id: str
    recommendations: List[MovieRecommendation]
    metadata: Dict[str, Any]

class MovieDetail(BaseModel):
    movie_id: str
    title: str
    description: Optional[str] = None
    poster_url: Optional[str] = None
    genres: Optional[List[str]] = None
    release_year: Optional[int] = None
    director: Optional[str] = None
    avg_rating: float = 0.0
    total_ratings: int = 0

class MovieListingResponse(BaseModel):
    movies: List[MovieDetail]
    count: int
    limit: int
    offset: int
