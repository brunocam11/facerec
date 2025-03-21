"""Configuration settings for the facial recognition service."""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
        env_prefix="",  # No prefix for environment variables
        env_nested_delimiter="__"  # Use double underscore for nested settings
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
    MODEL_PATH: str = "buffalo_l"
    
    # Worker Settings
    WORKER_IDLE_TIMEOUT: int = 120  # Default to 2 minutes (120 seconds) based on SQS alarm config
    SQS_BATCH_SIZE: int = 10  # Maximum allowed by SQS ReceiveMessage API
    
    # Pinecone Settings
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str
    
    # AWS Settings
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""
    AWS_S3_BUCKET_REGION: str = "us-east-1"
    
    # SQS Settings
    SQS_QUEUE_NAME: str = "facerec-indexing-staging-queue"

settings = Settings()
