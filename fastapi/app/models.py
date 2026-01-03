from pydantic import BaseModel
from typing import List, Optional

class MovieRecommendationRequest(BaseModel):
    user_id: int
    top_k: int = 10

class MovieRecommendationResponse(BaseModel):
    movie_id: int
    title: str
    score: float
