import asyncpg
import redis.asyncio as redis
from aiokafka import AIOKafkaProducer
import json
from .config import POSTGRES_DSN, REDIS_URL, KAFKA_BOOTSTRAP_SERVERS

# Global state for connections
class AppState:
    pg_pool: asyncpg.Pool = None
    redis_client: redis.Redis = None
    kafka_producer: AIOKafkaProducer = None

state = AppState()

async def init_resources():
    """Initialize all resources"""
    state.pg_pool = await asyncpg.create_pool(
        POSTGRES_DSN,
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    
    state.redis_client = await redis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )
    
    state.kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await state.kafka_producer.start()

async def close_resources():
    """Close all resources"""
    if state.redis_client:
        await state.redis_client.close()
    if state.pg_pool:
        await state.pg_pool.close()
    if state.kafka_producer:
        await state.kafka_producer.stop()

# Dependencies
async def get_db_pool() -> asyncpg.Pool:
    return state.pg_pool

async def get_redis() -> redis.Redis:
    return state.redis_client

async def get_kafka_producer() -> AIOKafkaProducer:
    return state.kafka_producer

# Auth Dependencies
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from .core.security import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from .repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db_pool)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(username)
    if user is None:
        raise credentials_exception
    return user
