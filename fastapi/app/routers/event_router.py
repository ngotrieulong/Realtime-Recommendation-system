from fastapi import APIRouter, Depends, Request
from typing import Dict, Any

from ..schemas.event import UserEvent
from ..dependencies import get_db_pool, get_kafka_producer
from ..repositories.log_repository import LogRepository
from ..services.event_service import EventService
from ..limiter import limiter

router = APIRouter()

async def get_event_service(
    db = Depends(get_db_pool),
    kafka_producer = Depends(get_kafka_producer)
) -> EventService:
    log_repo = LogRepository(db)
    return EventService(log_repo, kafka_producer)

@router.post("/api/events")
@limiter.limit("100/minute")
async def track_event(
    event: UserEvent,
    request: Request, # Required for limiter
    service: EventService = Depends(get_event_service)
):
    """
    Track user interaction event
    """
    return await service.track_event(event)
