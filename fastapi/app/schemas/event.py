from pydantic import BaseModel, Field
from typing import Optional

class UserEvent(BaseModel):
    """User interaction event"""
    user_id: str = Field(..., min_length=1, max_length=100)
    movie_id: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., pattern="^(click|view|play|rate|favorite|skip)$")
    rating: Optional[int] = Field(None, ge=1, le=5)
    watch_duration_sec: Optional[int] = Field(None, ge=0)
    session_id: Optional[str] = None
    rec_log_id: Optional[int] = None  # Link to recommendation that triggered this
