import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any
from aiokafka import AIOKafkaProducer

from ..repositories.log_repository import LogRepository
from ..schemas.event import UserEvent
from ..config import KAFKA_TOPIC_EVENTS

class EventService:
    def __init__(self, log_repo: LogRepository, kafka_producer: AIOKafkaProducer):
        self.log_repo = log_repo
        self.kafka_producer = kafka_producer

    async def track_event(self, event: UserEvent) -> Dict[str, str]:
        enriched_event = {
            **event.dict(),
            "timestamp": datetime.now().isoformat(),
            "server_timestamp": time.time()
        }
        
        # 1. Publish to Kafka
        if self.kafka_producer:
            try:
                await self.kafka_producer.send(
                    KAFKA_TOPIC_EVENTS,
                    value=enriched_event,
                    key=event.user_id.encode('utf-8')
                )
            except Exception as e:
                print(f"⚠️  Kafka publish failed: {e}")

        # 2. Log Feedback
        if event.rec_log_id:
            try:
                rec_log = await self.log_repo.get_log_entry(event.rec_log_id)
                if rec_log:
                    time_to_event_sec = int((datetime.now() - rec_log['timestamp']).total_seconds())
                    
                    # Find position
                    recs = json.loads(rec_log['recommended_movies']) if isinstance(rec_log['recommended_movies'], str) else rec_log['recommended_movies']
                    position = next(
                        (i + 1 for i, r in enumerate(recs) if r['movie_id'] == event.movie_id),
                        None
                    )
                    
                    await self.log_repo.log_feedback(
                        rec_log_id=event.rec_log_id,
                        movie_id=event.movie_id,
                        position=position,
                        event_type=event.event_type,
                        rating=event.rating,
                        watch_duration_sec=event.watch_duration_sec,
                        session_id=event.session_id or "unknown",
                        time_to_event_sec=time_to_event_sec
                    )
            except Exception as e:
                print(f"⚠️  Feedback logging failed: {e}")
        
        return {
            "status": "accepted",
            "message": "Event tracked successfully",
            "event_id": str(uuid.uuid4())
        }

    async def get_metrics(self) -> Dict[str, Any]:
        cache_stats = await self.log_repo.get_cache_stats()
        ctr_stats = await self.log_repo.get_ctr_stats()
        
        cache_hit_rate = (cache_stats['hits'] / cache_stats['total'] * 100) if cache_stats['total'] > 0 else 0
        ctr = (ctr_stats['clicks'] / ctr_stats['recommendations'] * 100) if ctr_stats['recommendations'] > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cache": {
                "total_requests": cache_stats['total'],
                "cache_hits": cache_stats['hits'],
                "hit_rate_percent": round(cache_hit_rate, 2)
            },
            "recommendations": {
                "total_served": ctr_stats['recommendations'],
                "total_clicks": ctr_stats['clicks'],
                "ctr_percent": round(ctr, 2)
            }
        }
