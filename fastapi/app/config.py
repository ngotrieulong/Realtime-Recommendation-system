import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@postgres/airflow")
    
    class Config:
        env_file = ".env"

settings = Settings()
