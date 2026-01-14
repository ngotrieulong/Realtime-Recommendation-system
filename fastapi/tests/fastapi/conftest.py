
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.dependencies import get_db_pool, get_redis, get_kafka_producer
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

@pytest.fixture
def mock_db_pool():
    pool = AsyncMock()
    # Mock connection context manager
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.fixture
def mock_kafka():
    return AsyncMock()

@pytest_asyncio.fixture
async def client(mock_db_pool, mock_redis, mock_kafka):
    # Override dependencies
    app.dependency_overrides[get_db_pool] = lambda: mock_db_pool
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_kafka_producer] = lambda: mock_kafka
    
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    from app.limiter import limiter
    limiter.enabled = False
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    limiter.enabled = True
    
    app.dependency_overrides = {}
