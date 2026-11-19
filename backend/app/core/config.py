import os
from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PROJECT_NAME: str = "CityFlow API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    
    # Path to local verifiable transit dataset
    NETWORK_DATA_PATH: str = os.getenv(
        "NETWORK_DATA_PATH",
        os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "data", "bengaluru", "network.json"
            )
        )
    )

    WALKING_SPEED_MPS: float = float(os.getenv("WALKING_SPEED_MPS", "1.2"))  # ~4.32 km/h
    TRANSFER_PENALTY_SEC: int = int(os.getenv("TRANSFER_PENALTY_SEC", "120"))  # 2 minutes
    WALKING_RADIUS_METERS: float = float(os.getenv("WALKING_RADIUS_METERS", "3000"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    USE_POSTGIS: bool = os.getenv("USE_POSTGIS", "false").lower() == "true"
    GEOAPIFY_API_KEY: str = os.getenv("GEOAPIFY_API_KEY", "")
    PHOTON_URL: str = os.getenv("PHOTON_URL", "http://127.0.0.1:2322")
    GEOCODING_TIMEOUT_SECONDS: float = float(os.getenv("GEOCODING_TIMEOUT_SECONDS", "4"))
    GEOCODING_CACHE_TTL_SECONDS: int = int(os.getenv("GEOCODING_CACHE_TTL_SECONDS", "604800"))
    GEOCODING_CONFIDENCE: float = float(os.getenv("GEOCODING_CONFIDENCE", "0.85"))
    GEOCODING_STREET_CONFIDENCE: float = float(os.getenv("GEOCODING_STREET_CONFIDENCE", "0.65"))
    GEOCODING_BUILDING_CONFIDENCE: float = float(os.getenv("GEOCODING_BUILDING_CONFIDENCE", "0.85"))

    # Kafka & Streaming Configuration
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TRAFFIC_TOPIC: str = os.getenv("KAFKA_TRAFFIC_TOPIC", "bengaluru.traffic.events.v1")
    KAFKA_TRANSIT_DELAY_TOPIC: str = os.getenv("KAFKA_TRANSIT_DELAY_TOPIC", "bengaluru.transit.delays.v1")
    KAFKA_CLIENT_ID: str = "cityflow-backend-producer"
    STREAMING_BUFFER_MAX_SIZE: int = int(os.getenv("STREAMING_BUFFER_MAX_SIZE", "500"))


settings = Settings()
