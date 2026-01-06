from fastapi import APIRouter, Depends

from ..dependencies import get_db_pool, get_kafka_producer
from ..repositories.log_repository import LogRepository
from ..services.event_service import EventService

router = APIRouter()

async def get_event_service(
    db = Depends(get_db_pool),
    kafka_producer = Depends(get_kafka_producer)
) -> EventService:
    log_repo = LogRepository(db)
    return EventService(log_repo, kafka_producer)

@router.get("/api/metrics")
async def get_metrics(
    service: EventService = Depends(get_event_service)
):
    """Get system metrics"""
    return await service.get_metrics()
