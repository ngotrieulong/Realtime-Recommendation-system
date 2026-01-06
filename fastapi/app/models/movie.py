from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MovieDB(Base):
    """
    ORM Model - Mapping 1-1 with table 'movies' in Postgres
    """
    __tablename__ = 'movies'
    
    id = Column(Integer, primary_key=True)
    movie_id = Column(String(50), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    genres = Column(JSON)  # ["Action", "Drama"]
    avg_rating = Column(Float)
    poster_url = Column(String(500))
    embedding = Column(JSON)  # Vector [0.1, 0.2, ...]
    created_at = Column(DateTime)
    description = Column(String) 
    release_year = Column(Integer)
    director = Column(String)
    total_ratings = Column(Integer)

class BatchRecommendationDB(Base):
    __tablename__ = 'batch_recommendations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False)
    recommendations = Column(JSON)  # List of movie_ids
    model_version = Column(String(50))
    computed_at = Column(DateTime)
    expires_at = Column(DateTime)
