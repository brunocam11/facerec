"""
S3 service for object storage operations.
"""
import logging
import boto3
from typing import BinaryIO, Optional, List, Dict, Any
from fastapi import FastAPI
from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    """Service for interacting with AWS S3 for image storage."""
    
    def __init__(
        self, 
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None
    ):
        """
        Initialize the S3 service with AWS credentials.
        
        Args:
            bucket_name: S3 bucket name (defaults to settings)
            region_name: AWS region name (defaults to settings)
            access_key_id: AWS access key ID (defaults to settings)
            secret_access_key: AWS secret access key (defaults to settings)
        """
        self.bucket_name = bucket_name or settings.AWS_S3_BUCKET
        # Always use AWS_REGION for consistency
        self.region_name = region_name or settings.AWS_REGION
        self.access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY
        self.s3 = None
        self.initialized = False
    
    async def initialize(self) -> None:
        """Initialize the S3 client."""
        if self.initialized:
            return
        
        try:
            logger.info(f"Initializing S3 service for bucket: {self.bucket_name}")
            
            # Default to us-east-1 if region is empty
            if not self.region_name:
                self.region_name = "us-east-1"
                logger.info("Using default region us-east-1")
            
            self.s3 = boto3.client(
                's3',
                region_name=self.region_name,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key
            )
            
            # Verify bucket exists
            self.s3.head_bucket(Bucket=self.bucket_name)
            
            logger.info(f"Successfully initialized S3 service for bucket: {self.bucket_name}")
            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize S3 service: {str(e)}")
            raise
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up S3 service resources")
        # The boto3 client doesn't need explicit cleanup
        self.initialized = False
    
    async def upload_file(self, file_obj: BinaryIO, key: str) -> str:
        """
        Upload a file to S3.
        
        Args:
            file_obj: File-like object to upload
            key: S3 object key
            
        Returns:
            The S3 object URL
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            self.s3.upload_fileobj(file_obj, self.bucket_name, key)
            url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"
            logger.info(f"Successfully uploaded file to S3: {key}")
            return url
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            raise
    
    async def get_file_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.
        
        Args:
            key: S3 object key
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL for the object
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise
    
    async def list_objects(self, prefix: str = '', max_keys: int = 1000) -> List[Dict[str, Any]]:
        """
        List objects in the S3 bucket with a given prefix.
        
        Args:
            prefix: Key prefix to filter objects
            max_keys: Maximum number of keys to return
            
        Returns:
            List of object metadata
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag']
                    })
            
            return objects
        except Exception as e:
            logger.error(f"Failed to list objects in S3: {str(e)}")
            raise
            
    async def list_albums(self, max_keys: int = 1000) -> List[str]:
        """
        List album folders in the bucket.
        
        This is a helper method to identify album-like prefixes by finding common prefixes.
        
        Args:
            max_keys: Maximum number of keys to return
            
        Returns:
            List of album folder prefixes
        """
        if not self.initialized:
            await self.initialize()
            
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Delimiter='/',
                MaxKeys=max_keys
            )
            
            albums = []
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    # Remove trailing slash
                    album = prefix['Prefix'].rstrip('/')
                    albums.append(album)
            
            return albums
        except Exception as e:
            logger.error(f"Failed to list albums in S3: {str(e)}")
            raise 