
import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation ID (request_id) and log request timing.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # 1. Generate or retrieve Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add to request state so downstream can use it
        request.state.request_id = request_id
        
        # 2. Start Timer
        start_time = time.time()
        
        # 3. Log Request Start (Optional, can be noisy)
        # logger.info("Request started", extra={"request_id": request_id, "path": request.url.path, "method": request.method})

        # 4. Process Request
        try:
            response = await call_next(request)
            
            # 5. Add Request ID and Process Time to Response Headers
            process_time = (time.time() - start_time) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # 6. Calculate Duration (already done above)

            
            # 7. Log Request Completion
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round(process_time, 2),
                    "user_agent": request.headers.get("user-agent"),
                }
            )
            
            return response
            
        except Exception as e:
            # Log exception with context (Middleware usually catches unhandled ones if not caught by exception handlers)
            # However, ExceptionMiddleware usually runs outside this, so we might see it re-raised.
            # We log it here just in case.
            process_time = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": round(process_time, 2),
                    "error": str(e)
                },
                exc_info=True
            )
            raise e
