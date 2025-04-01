"""Service for handling file operations including S3 retrieval."""
from typing import Optional

from app.core.exceptions import FileServiceError
from app.core.logging import get_logger
from app.services.aws.s3 import S3Service

logger = get_logger(__name__)

class FileService:
    """Service for handling file operations."""
    
    def __init__(self, s3_service: S3Service):
        """Initialize the file service.
        
        Args:
            s3_service: S3 service instance
        """
        self.s3_service = s3_service
    
    async def get_file_bytes(self, bucket: str, object_key: str) -> bytes:
        """Get file bytes from S3.
        
        Args:
            bucket: S3 bucket name
            object_key: S3 object key
            
        Returns:
            File bytes
            
        Raises:
            FileServiceError: If file retrieval fails
        """
        try:
            # Ensure S3 client is initialized
            if not self.s3_service.initialized:
                await self.s3_service.initialize()
            
            # Get file from S3
            response = self.s3_service.s3.get_object(Bucket=bucket, Key=object_key)
            return response['Body'].read()
            
        except Exception as e:
            logger.error(
                "Failed to get file from S3",
                bucket=bucket,
                object_key=object_key,
                error=str(e),
                exc_info=True
            )
            raise FileServiceError(f"Failed to get file from S3: {str(e)}") 