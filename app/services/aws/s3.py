"""
S3 service for object storage operations using aioboto3.
"""
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, BinaryIO, Dict, List, Optional
import os

import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Service:
    """Service for interacting with AWS S3 using aioboto3."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None
    ):
        """Store configuration but do not initialize client yet."""
        self.bucket_name = bucket_name or settings.AWS_S3_BUCKET
        self.region_name = region_name or settings.AWS_REGION
        self.access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY
        # Client will be initialized asynchronously
        self._s3_client = None
        self._session = aioboto3.Session()

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[Any, None]:
        """Async context manager to get or initialize the S3 client."""
        if self._s3_client is None:
            logger.debug("Initializing aioboto3 S3 client")
            client_args = {
                'region_name': self.region_name or "us-east-1"
            }
            if self.access_key_id and self.secret_access_key:
                logger.debug(
                    "Using explicit AWS credentials from config for aioboto3")
                client_args['aws_access_key_id'] = self.access_key_id
                client_args['aws_secret_access_key'] = self.secret_access_key
            else:
                logger.debug(
                    "Allowing aioboto3 to discover AWS credentials automatically")

            # Create client within context manager for proper cleanup
            try:
                async with self._session.client("s3", **client_args) as s3:
                    # Quick check to ensure connection is valid (optional but good)
                    # await s3.head_bucket(Bucket=self.bucket_name)
                    # logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
                    self._s3_client = s3
                    yield s3
            except NoCredentialsError as e:
                logger.error(
                    f"Failed to initialize S3: AWS credentials not found. {e}")
                raise StorageError(
                    f"AWS credentials not found or configured correctly.")
            except ClientError as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                raise StorageError(f"Failed to initialize S3 client: {e}")
            except Exception as e:
                logger.error(
                    f"Unexpected error initializing S3 client: {e}", exc_info=True)
                raise StorageError(f"Unexpected error initializing S3: {e}")
        else:
            yield self._s3_client

    async def upload_file(self, file_obj: BinaryIO, key: str) -> str:
        """
        Upload a file to S3 asynchronously.

        Args:
            file_obj: File-like object to upload
            key: S3 object key

        Returns:
            The S3 object URL
        """
        try:
            async with self._get_client() as s3:
                await s3.upload_fileobj(file_obj, self.bucket_name, key)
            url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"
            logger.info("Successfully uploaded file to S3",
                        key=key, bucket=self.bucket_name)
            return url
        except ClientError as e:
            logger.error("Failed to upload file to S3 due to client error",
                         key=key, error=e, exc_info=True)
            raise StorageError(
                f"Failed to upload file '{key}' to S3: {e}") from e
        except Exception as e:
            logger.error("Unexpected error uploading file to S3",
                         key=key, error=e, exc_info=True)
            raise StorageError(
                f"Unexpected error uploading file '{key}': {e}") from e

    async def get_file_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL asynchronously.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL for the object
        """
        try:
            async with self._get_client() as s3:
                url = await s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )
            logger.debug("Generated presigned URL",
                         key=key, bucket=self.bucket_name)
            return url
        except ClientError as e:
            logger.error("Failed to generate presigned URL due to client error",
                         key=key, error=e, exc_info=True)
            raise StorageError(
                f"Failed to generate presigned URL for '{key}': {e}") from e
        except Exception as e:
            logger.error("Unexpected error generating presigned URL",
                         key=key, error=e, exc_info=True)
            raise StorageError(
                f"Unexpected error generating presigned URL for '{key}': {e}") from e

    async def list_objects(self, prefix: str = '', max_keys: int = 1000) -> List[Dict[str, Any]]:
        """
        List objects asynchronously using paginator.

        Args:
            prefix: Key prefix to filter objects
            max_keys: Maximum number of keys to return

        Returns:
            List of object metadata
        """
        objects = []
        try:
            async with self._get_client() as s3:
                paginator = s3.get_paginator('list_objects_v2')
                # Use async for with the paginator
                async for page in paginator.paginate(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    PaginationConfig={'MaxItems': max_keys}
                ):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            objects.append({
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'],
                                'etag': obj['ETag']
                            })
                            if len(objects) >= max_keys:
                                break
                    if len(objects) >= max_keys:
                        break

            logger.debug("Listed objects", prefix=prefix, count=len(objects))
            return objects
        except ClientError as e:
            logger.error("Failed to list objects in S3 due to client error",
                         prefix=prefix, error=e, exc_info=True)
            raise StorageError(
                f"Failed to list objects with prefix '{prefix}': {e}") from e
        except Exception as e:
            logger.error("Unexpected error listing objects in S3",
                         prefix=prefix, error=e, exc_info=True)
            raise StorageError(
                f"Unexpected error listing objects with prefix '{prefix}': {e}") from e

    async def list_albums(self, max_keys: int = 1000) -> List[str]:
        """
        List albums asynchronously using paginator.

        This is a helper method to identify album-like prefixes by finding common prefixes.

        Args:
            max_keys: Maximum number of keys to return

        Returns:
            List of album folder prefixes
        """
        albums = []
        try:
            async with self._get_client() as s3:
                paginator = s3.get_paginator('list_objects_v2')
                async for page in paginator.paginate(
                    Bucket=self.bucket_name,
                    Delimiter='/',
                    PaginationConfig={'MaxItems': max_keys}
                ):
                    if 'CommonPrefixes' in page:
                        for prefix_data in page['CommonPrefixes']:
                            album = prefix_data['Prefix'].rstrip('/')
                            albums.append(album)
                            if len(albums) >= max_keys:
                                break
                    if len(albums) >= max_keys:
                        break
            logger.debug("Listed albums", count=len(albums))
            return albums
        except ClientError as e:
            logger.error(
                "Failed to list albums in S3 due to client error", error=e, exc_info=True)
            raise StorageError(f"Failed to list albums: {e}") from e
        except Exception as e:
            logger.error("Unexpected error listing albums in S3",
                         error=e, exc_info=True)
            raise StorageError(f"Unexpected error listing albums: {e}") from e

    async def get_file(self, bucket: str, key: str) -> bytes:
        """
        Get file contents from S3 asynchronously.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            File contents as bytes

        Raises:
            StorageError: If file cannot be retrieved (e.g., not found, access denied)
        """
        target_bucket = bucket if bucket else self.bucket_name
        if target_bucket != self.bucket_name:
            logger.warning(
                f"Accessing S3 bucket '{target_bucket}' different from initialized bucket '{self.bucket_name}'")

        try:
            async with self._get_client() as s3:
                response = await s3.get_object(Bucket=target_bucket, Key=key)
                # Read from the async body stream
                body = response['Body']
                content = await body.read()
                return content
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found in S3: {target_bucket}/{key}")
                raise StorageError(f"File not found: {key}") from e
            elif error_code == 'NoSuchBucket':
                logger.error(
                    f"Attempted to get file from non-existent bucket: {target_bucket}")
                raise StorageError(f"Bucket not found: {target_bucket}") from e
            elif error_code == '403' or "Forbidden" in str(e) or "Access Denied" in str(e):
                logger.error(
                    f"Access denied when getting file: {target_bucket}/{key}. Check permissions. {e}")
                raise StorageError(f"Access denied for file: {key}") from e
            else:
                logger.error(
                    f"Failed to get file from S3 due to client error: {e}", exc_info=True)
                raise StorageError(
                    f"Failed to retrieve file '{key}' due to S3 error: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error getting file from S3: {target_bucket}/{key} - {e}", exc_info=True)
            raise StorageError(
                f"Unexpected error retrieving file: {key}") from e

    async def download_file(self, bucket: str, key: str, file_path: str) -> None:
        """Download an object directly to a file path asynchronously.

        Args:
            bucket: S3 bucket name
            key: S3 object key
            file_path: Local path to save the downloaded file

        Raises:
            StorageError: If file cannot be downloaded
        """
        target_bucket = bucket if bucket else self.bucket_name
        if target_bucket != self.bucket_name:
            logger.warning(
                f"Downloading from S3 bucket '{target_bucket}' different from initialized bucket '{self.bucket_name}'")

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            async with self._get_client() as s3:
                logger.debug(f"Starting download: s3://{target_bucket}/{key} to {file_path}")
                await s3.download_file(
                    Bucket=target_bucket,
                    Key=key,
                    Filename=file_path
                )
            logger.info(f"Successfully downloaded s3://{target_bucket}/{key} to {file_path}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404' or 'Not Found' in str(e):
                logger.warning(f"File not found during download attempt: s3://{target_bucket}/{key}")
                raise StorageError(f"File not found: {key}") from e
            elif error_code == 'NoSuchBucket':
                 logger.error(
                    f"Attempted to download from non-existent bucket: {target_bucket}")
                 raise StorageError(f"Bucket not found: {target_bucket}") from e
            elif error_code == '403' or "Forbidden" in str(e) or "Access Denied" in str(e):
                logger.error(
                    f"Access denied when downloading file: {target_bucket}/{key}. Check permissions. {e}")
                raise StorageError(f"Access denied for file: {key}") from e
            else:
                logger.error(
                    f"Failed to download file from S3 due to client error: {target_bucket}/{key} - {e}", exc_info=True)
                raise StorageError(
                    f"Failed to download file '{key}' due to S3 error: {e}") from e
        except Exception as e:
             logger.error(
                f"Unexpected error downloading file from S3: {target_bucket}/{key} - {e}", exc_info=True)
             raise StorageError(
                f"Unexpected error downloading file: {key}") from e
