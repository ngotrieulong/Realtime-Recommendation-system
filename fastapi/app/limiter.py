
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Use Redis for rate limiting storage if available
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Initialize Limiter
# key_func: determines how to identify the user (IP address by default)
# storage_uri: where to store the limits (memory or redis)
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDIS_URL,
    default_limits=["100/minute"]  # Global default limit
)
