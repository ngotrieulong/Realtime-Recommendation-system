"""
=============================================================================
ENHANCED FASTAPI - Movie Recommendation System (Restructured)
=============================================================================
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from .routers import recommendation_router, event_router, metrics_router, auth_router
from .dependencies import init_resources, close_resources
from .logging_config import setup_logging
from .middleware import RequestTrackingMiddleware
from .exceptions import global_exception_handler, http_exception_handler, validation_exception_handler
from .limiter import limiter

# =============================================================================
# LOGGING SETUP
# =============================================================================
setup_logging()

# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(
    title="Movie Recommendation API",
    description="Production-ready recommendation system with Lambda Architecture",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Set up limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Set up Prometheus instrumentation
instrumentator = Instrumentator().instrument(app).expose(app)

# =============================================================================
# MIDDLEWARE
# =============================================================================
app.add_middleware(SlowAPIMiddleware) # Must be added to handle RateLimit exceptions properly? Actually, exception handler does it.
# SlowAPIMiddleware is deprecated in newer versions? Wait, the docs say:
# "Add SlowAPIMiddleware to your app." -> app.add_middleware(SlowAPIMiddleware)
# But standard FastAPI exception handler handles it. 
# Let's keep it safe.

app.add_middleware(RequestTrackingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# =============================================================================
# ROUTERS
# =============================================================================
app.include_router(auth_router.router)
app.include_router(recommendation_router.router)
app.include_router(event_router.router)
app.include_router(metrics_router.router)


@app.get("/health")
async def health_check():
    from .dependencies import state
    from datetime import datetime
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "components": {
            "postgres": "unknown",
            "redis": "unknown"
        }
    }
    
    # Check Postgres
    try:
        if state.pg_pool:
            async with state.pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            health_status["components"]["postgres"] = "up"
        else:
            health_status["components"]["postgres"] = "down (not initialized)"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["postgres"] = f"down: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        if state.redis_client:
            await state.redis_client.ping()
            health_status["components"]["redis"] = "up"
        else:
            health_status["components"]["redis"] = "down (not initialized)"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["redis"] = f"down: {str(e)}"
        health_status["status"] = "unhealthy"

    return health_status

# =============================================================================
# STARTUP & SHUTDOWN
# =============================================================================
@app.on_event("startup")
async def startup():
    await init_resources()
    print("✅ All connections initialized")

@app.on_event("shutdown")
async def shutdown():
    await close_resources()
    print("👋 All connections closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)