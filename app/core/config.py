"""Configuration settings for the facial recognition service."""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env"
    )

    # Core Settings
    PROJECT_NAME: str = "Face Recognition Service"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # CORS Settings
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        """Get list of allowed origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    # Face Recognition Settings
    MAX_FACES_PER_IMAGE: int = 20
    MIN_FACE_CONFIDENCE: float = 0.9
    SIMILARITY_THRESHOLD: float = 0.8
    MODEL_CACHE_DIR: str = ".model_cache"
    MAX_IMAGE_PIXELS: int = 1920 * 1080  # ~2MP (Full HD)
    MAX_MATCHES: int = 100  # Maximum number of matches to return from search
    
    # API Settings
    MAX_CONCURRENT_REQUESTS: int = 50
    REQUEST_TIMEOUT_SECONDS: int = 30

    # Pinecone Settings
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    MODEL_PATH: str = "buffalo_l"

    # AWS Settings
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""
    AWS_S3_BUCKET_REGION: str = "us-east-1"

    # Image Processing Settings
    JPEG_QUALITY: int = 85  # Good balance of quality/size

settings = Settings()
