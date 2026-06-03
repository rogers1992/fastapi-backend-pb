from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Paraiso Biker API"
    VERSION: str = "1.0.0"
    DATABASE_URL: str = "postgresql://postgres:paraiso2026secure@localhost:5432/paraiso_biker"
    SECRET_KEY: str = "a8f5f167f44f4964e6c998dee827110c3f8f9b8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
