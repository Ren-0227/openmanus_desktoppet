# config.py
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    WEBSOCKET_HOST: str = os.getenv("WEBSOCKET_HOST", "localhost")
    WEBSOCKET_PORT: int = os.getenv("WEBSOCKET_PORT", 8765)
    HEALTH_CHECK_INTERVAL: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()