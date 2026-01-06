
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

logger = logging.getLogger(__name__)

class MovieRecommendationException(Exception):
    """Base exception for the application"""
    pass

class ServiceUnavailableException(MovieRecommendationException):
    pass

async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler to execute last (if registered appropriately).
    Returns 500 JSON response and hides internal error details in production.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        "Unhandled exception occurred",
        extra={"request_id": request_id, "path": request.url.path},
        exc_info=exc
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please contact support.",
            "request_id": request_id
        },
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle standard FastAPI HTTPExceptions.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log 5xx errors as errors, 4xx as warnings or info
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} error", extra={"request_id": request_id, "detail": exc.detail})
    else:
        logger.info(f"HTTP {exc.status_code} error", extra={"request_id": request_id, "detail": exc.detail})
        
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "request_id": request_id},
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic validation errors.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info("Validation error", extra={"request_id": request_id, "errors": exc.errors()})
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "details": exc.errors(),
            "request_id": request_id
        },
    )
