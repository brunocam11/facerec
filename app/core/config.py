"""Configuration settings for the facial recognition service."""
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.
    
    These settings are loaded from environment variables with the following precedence:
    1. Environment variables
    2. .env file
    3. Default values
    
    Attributes:
        PINECONE_API_KEY: API key for Pinecone vector database
        PINECONE_INDEX_NAME: Name of the Pinecone index to use
        SIMILARITY_THRESHOLD: Default similarity threshold for face matching (0-100)
    """
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
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
    MODEL_CACHE_DIR: str = ".model_cache"
    MAX_IMAGE_PIXELS: int = 1920 * 1080  # ~2MP (Full HD)
    MAX_MATCHES: int = 100  # Maximum number of matches to return from search
    MODEL_PATH: str = "buffalo_l"
    
    # Worker Settings
    WORKER_IDLE_TIMEOUT: int = 120  # Default to 2 minutes (120 seconds) based on SQS alarm config
    SQS_BATCH_SIZE: int = 10  # Maximum allowed by SQS ReceiveMessage API
    
    # Pinecone Settings
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str = "face-recognition"
    
    # AWS Settings
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""
    AWS_S3_BUCKET_REGION: str = "us-east-1"
    
    # SQS Settings
    SQS_QUEUE_NAME: str = "facerec-indexing-staging-queue"

    # Face matching settings
    SIMILARITY_THRESHOLD: float = 80.0

    # Optional settings with defaults
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

settings = Settings()
