from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

class AppClientDB(Base):
    __tablename__ = "app_clients"

    client_id = Column(String, primary_key=True)
    client_secret_hash = Column(String, nullable=False)
    app_name = Column(String, nullable=False)
    rate_limit_tier = Column(String, default="standard") # standard, premium
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
