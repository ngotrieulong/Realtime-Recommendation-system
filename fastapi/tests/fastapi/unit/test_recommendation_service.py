
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.recommendation_service import RecommendationService
from app.repositories.movie_repository import MovieRepository
from app.repositories.log_repository import LogRepository

@pytest.fixture
def mock_movie_repo():
    return AsyncMock(spec=MovieRepository)

@pytest.fixture
def mock_log_repo():
    return AsyncMock(spec=LogRepository)

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.get.return_value = None # Cache miss by default
    return mock

@pytest.mark.asyncio
async def test_get_recommendations_cache_hit(mock_movie_repo, mock_log_repo, mock_redis):
    # Arrange
    import json
    from datetime import datetime, timedelta
    
    mock_redis.get.return_value = json.dumps({
        "recommendations": [{"movie_id": "m1", "score": 0.9}],
        "source": "cached_source",
        "valid_until": (datetime.now() + timedelta(hours=1)).isoformat()
    })
    
    service = RecommendationService(mock_movie_repo, mock_log_repo, mock_redis)
    request = MagicMock()
    
    # Act
    result = await service.get_recommendations("user1", 10, "session1", request)
    
    # Assert
    assert result['metadata']['cached'] is True
    assert result['metadata']['source'] == "cached_source"
    mock_movie_repo.get_batch_recommendations.assert_not_called()

@pytest.mark.asyncio
async def test_get_recommendations_hybrid_blend(mock_movie_repo, mock_log_repo, mock_redis):
    # Arrange
    # Batch returns M1 (0.9), M2 (0.8)
    mock_movie_repo.get_batch_recommendations.return_value = [
        {"movie_id": "m1", "score": 0.9},
        {"movie_id": "m2", "score": 0.8}
    ]
    # Realtime returns M2 (0.9), M3 (0.7)
    # Mock private method _compute_realtime (simulated via side effect or patching, 
    # but here we can mock if we subclass or patch, but simpler to mock repo calls)
    
    # Since _compute_realtime calls get_user_profile...
    mock_movie_repo.get_user_profile.return_value = [0.1, 0.2] 
    mock_movie_repo.get_watched_movies.return_value = []
    mock_movie_repo.find_similar_movies.return_value = [
         {"movie_id": "m2", "title": "M2", "poster_url": None, "similarity_score": 0.9},
         {"movie_id": "m3", "title": "M3", "poster_url": None, "similarity_score": 0.7}
    ]

    service = RecommendationService(mock_movie_repo, mock_log_repo, mock_redis)
    request = MagicMock()
    
    # Act
    result = await service.get_recommendations("user1", 10, "session1", request)
    
    # Assert
    # Logic:
    # M1 score = 0.9 * 0.7 (BATCH_WEIGHT) = 0.63
    # M2 score = (0.8 * 0.7) + (0.9 * 0.3) = 0.56 + 0.27 = 0.83
    # M3 score = 0.7 * 0.3 = 0.21
    # Order should be M2, M1, M3
    
    recs = result['recommendations']
    assert len(recs) == 3
    assert recs[0]['movie_id'] == "m2"
    assert recs[1]['movie_id'] == "m1"
    assert recs[2]['movie_id'] == "m3"
    assert result['metadata']['source'] == "hybrid"

@pytest.mark.asyncio
async def test_get_recommendations_fallback_popular(mock_movie_repo, mock_log_repo, mock_redis):
    # Arrange
    mock_movie_repo.get_batch_recommendations.return_value = []
    mock_movie_repo.get_user_profile.return_value = None # No profile = No realtime
    
    mock_movie_repo.get_popular_movies.return_value = [
        {"movie_id": "p1", "title": "P1", "poster_url": None, "score": 4.5}
    ]
    
    service = RecommendationService(mock_movie_repo, mock_log_repo, mock_redis)
    request = MagicMock()
    
    # Act
    result = await service.get_recommendations("user1", 10, "session1", request)
    
    # Assert
    assert result['metadata']['source'] == "popular"
    assert result['recommendations'][0]['movie_id'] == "p1"
