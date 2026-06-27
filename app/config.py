from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Paraiso Biker API"
    VERSION: str = "1.0.0"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/paraiso_biker"
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_A_RANDOM_SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    DEBUG: bool = False
    SEED_DEFAULTS: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
