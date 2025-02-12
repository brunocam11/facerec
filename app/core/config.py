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
    PINECONE_ENVIRONMENT: str
    PINECONE_INDEX_NAME: str = "face-recognition"

    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "facerec"
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10
    POSTGRES_POOL_TIMEOUT: int = 30

    # Image Processing Settings
    JPEG_QUALITY: int = 85  # Good balance of quality/size

    @property
    def database_url(self) -> str:
        """Get async PostgreSQL database URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
