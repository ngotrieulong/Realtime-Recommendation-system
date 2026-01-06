from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RecommendationLogDB(Base):
    __tablename__ = 'recommendation_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))
    session_id = Column(String(100))
    recommended_movies = Column(JSON)
    algorithm_source = Column(String(50))
    context = Column(JSON)
    total_candidates = Column(Integer)
    computation_time_ms = Column(Integer)
    cache_hit = Column(Boolean)
    timestamp = Column(DateTime)

class RecommendationFeedbackDB(Base):
    __tablename__ = 'recommendation_feedback'
    
    id = Column(Integer, primary_key=True)
    rec_log_id = Column(Integer)
    movie_id = Column(String(50))
    position_in_list = Column(Integer)
    event_type = Column(String(50))
    rating = Column(Integer)
    watch_duration_sec = Column(Integer)
    timestamp = Column(DateTime)
    time_to_event_sec = Column(Integer)
    session_id = Column(String(100))
