import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Leafline API Gateway & Orchestrator"
    VERSION: str = "1.0.0"
    PORT: int = int(os.getenv("PORT", "8080"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    # Microservice URLs (configurable via environment variables for local or docker)
    PLANT_SERVICE_URL: str = os.getenv("PLANT_SERVICE_URL", "http://127.0.0.1:8000")
    WEATHER_SERVICE_URL: str = os.getenv("WEATHER_SERVICE_URL", "http://127.0.0.1:8001")
    SOIL_SERVICE_URL: str = os.getenv("SOIL_SERVICE_URL", "http://127.0.0.1:8091")
    
    # Request timeouts in seconds
    SERVICE_TIMEOUT_SECONDS: float = float(os.getenv("SERVICE_TIMEOUT_SECONDS", "5.0"))
    
    # CORS
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,*").split(",")
        if origin.strip()
    ]

settings = Settings()
