"""
Worker script for consuming and processing facial recognition indexing tasks.
"""
from app.services import face_indexing
from app.core.exceptions import NoFaceDetectedError
from app.core.container import ServiceContainer, container
from app.core.config import settings
import boto3
import asyncio
import json
import logging
import os
import signal
import sys
import time
import traceback
import requests
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import cpu_count
from typing import Any, Dict, List, Optional, Tuple

# Add the parent directory to the path for module imports
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), '../../../')))


logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False
# Global model cache for each process
_model_cache = {}


@dataclass
class ProcessingResult:
    """Result of processing a single message."""
    job_id: str
    success: bool
    receipt_handle: str
    error_message: Optional[str] = None
    face_ids: Optional[List[str]] = None


def configure_logging():
    """Configure logging for the worker."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("worker.log")
        ]
    )
    # Set boto3 and botocore loggers to WARNING to reduce noise
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)


def setup_termination_handler():
    """Setup signal handlers for graceful termination."""
    def handler(signum, frame):
        global shutdown_flag
        signame = signal.Signals(signum).name
        logger.info(
            f"Received signal {signame} ({signum}), shutting down gracefully")
        shutdown_flag = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def check_spot_termination():
    """Check if spot instance is scheduled for termination."""
    try:
        response = requests.get(
            "http://169.254.169.254/latest/meta-data/spot/termination-time",
            timeout=1
        )
        if response.status_code == 200:
            logger.warning("Spot instance scheduled for termination")
            return True
    except Exception:
        # Any failure here should be ignored - we're just checking
        pass
    return False


def init_aws_environment():
    """Initialize AWS-specific environment variables and configurations."""
    try:
        logger.info("Initializing AWS environment")
        # Set default AWS region if not specified
        if not os.environ.get('AWS_REGION'):
            os.environ['AWS_REGION'] = settings.AWS_REGION
            
        # Try to get instance ID for identification
        try:
            instance_id_response = requests.get(
                "http://169.254.169.254/latest/meta-data/instance-id", 
                timeout=1
            )
            if instance_id_response.status_code == 200:
                instance_id = instance_id_response.text
                logger.info(f"Running on EC2 instance: {instance_id}")
        except Exception:
            logger.info("Not running on EC2 or unable to get instance metadata")
    except Exception as e:
        logger.warning(f"Error initializing AWS environment: {e}")


def init_service_container():
    """Initialize the service container for the main process."""
    return asyncio.run(container.initialize(None))


def get_indexing_service():
    """
    Get a cached instance of the indexing service for the current process.

    This ensures we don't initialize the model for every single image.
    For worker processes, we need to create a new service using 
    the face recognition service and vector store from the container.
    """
    # Use process ID as a key to ensure each process has its own model
    pid = os.getpid()

    if pid not in _model_cache:
        logger.info(f"Initializing face recognition model for process {pid}")

        try:
            # For the main process, we can use the one from the container
            if pid == os.getppid():
                if not container.face_recognition_service or not container.vector_store:
                    raise RuntimeError("Container services not initialized")
                _model_cache[pid] = face_indexing.FaceIndexingService(
                    face_service=container.face_recognition_service,
                    vector_store=container.vector_store
                )
            else:
                # For worker processes, we need to initialize new instances
                # This is simplified for testing - in production, this should be more efficient
                from app.services import InsightFaceRecognitionService
                from app.infrastructure.vectordb import PineconeVectorStore

                face_service = InsightFaceRecognitionService()
                vector_store = PineconeVectorStore()

                _model_cache[pid] = face_indexing.FaceIndexingService(
                    face_service=face_service,
                    vector_store=vector_store
                )

            logger.info(f"Successfully initialized model for process {pid}")
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(
                f"Failed to initialize model for process {pid}: {str(e)}\n{error_details}")
            raise

    return _model_cache[pid]


def download_s3_image(
    s3_client,
    bucket: str,
    key: str,
    local_path: str
) -> bool:
    """
    Download an image from S3 to a local path.

    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key
        local_path: Local path to save the image

    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        logger.debug(f"Downloading S3 image {bucket}/{key} to {local_path}")
        s3_client.download_file(bucket, key, local_path)
        return True
    except Exception as e:
        logger.error(f"Failed to download S3 image {bucket}/{key}: {str(e)}")
        return False


def process_single_message(
    message: Dict[str, Any],
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str
) -> ProcessingResult:
    """
    Process a single SQS message in a separate process.

    This function runs in a separate process and handles a single face indexing task.

    Args:
        message: SQS message containing job details
        region: AWS region
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Returns:
        ProcessingResult with job status and details
    """
    # Extract message details
    receipt_handle = message['receipt_handle']
    body = message['body']
    job_id = body.get('job_id', 'unknown')

    try:
        # Extract indexing parameters
        collection_id = body.get('collection_id')
        image_id = body.get('image_id')
        s3_bucket = body.get('s3_bucket')
        s3_key = body.get('s3_key')
        max_faces = body.get('max_faces', 5)

        if not all([collection_id, image_id, s3_bucket, s3_key]):
            raise ValueError("Missing required parameters in message body")

        logger.info(
            f"Processing job {job_id}: image {image_id} for collection {collection_id}")

        # Set up process-specific S3 client
        s3_client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        # Download image from S3 to a temporary location
        temp_dir = f"/tmp/facerec/{job_id}"
        os.makedirs(temp_dir, exist_ok=True)
        local_image_path = f"{temp_dir}/{os.path.basename(image_id)}"

        # Download image
        start_time = time.time()
        success = download_s3_image(
            s3_client, s3_bucket, s3_key, local_image_path)
        if not success:
            raise RuntimeError(
                f"Failed to download image from S3: {s3_bucket}/{s3_key}")
        download_time = time.time() - start_time
        logger.debug(f"Downloaded image in {download_time:.2f} seconds")

        # Use cached indexing service
        start_time = time.time()
        indexing_service = get_indexing_service()

        # Process the image
        with open(local_image_path, 'rb') as img_file:
            # For testing, we can't use async in a normal process, so we'll simulate async
            # In production, this would be properly handled with async support
            image_bytes = img_file.read()
            # Simulate async call
            try:
                indexing_result = asyncio.run(indexing_service.index_faces(
                    collection_id=collection_id,
                    image_id=image_id,
                    image_bytes=image_bytes,
                    max_faces=max_faces
                ))

                # Extract face IDs from result
                face_ids = [
                    face.face_id for face in indexing_result.face_records]
                processing_time = time.time() - start_time
                logger.info(
                    f"Successfully processed job {job_id}: found {len(face_ids)} faces in {processing_time:.2f} seconds")

                return ProcessingResult(
                    job_id=job_id,
                    success=True,
                    receipt_handle=receipt_handle,
                    face_ids=face_ids
                )
            except NoFaceDetectedError:
                # Not an error - just no faces found
                processing_time = time.time() - start_time
                logger.info(
                    f"No faces detected in image for job {job_id} - recording as successful processing ({processing_time:.2f} seconds)")
                return ProcessingResult(
                    job_id=job_id,
                    success=True,  # Mark as successful even with no faces
                    receipt_handle=receipt_handle,
                    face_ids=[]    # Empty list of face IDs
                )

        # Clean up temporary files
        try:
            os.remove(local_image_path)
            if len(os.listdir(temp_dir)) == 0:
                os.rmdir(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {str(e)}")

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(
            f"Error processing job {job_id}: {str(e)}\n{error_details}")
        return ProcessingResult(
            job_id=job_id,
            success=False,
            receipt_handle=receipt_handle,
            error_message=str(e)
        )


async def process_messages(
    sqs_service,
    region: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    batch_size: int = 10,
    max_workers: Optional[int] = None,
) -> None:
    """
    Process messages from the SQS queue using a process pool.

    Args:
        sqs_service: SQS service instance
        region: AWS region
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        batch_size: Number of messages to process in parallel
        max_workers: Maximum number of worker processes
    """
    if max_workers is None:
        # Leave one CPU for the main process
        max_workers = max(1, cpu_count() - 1)

    logger.info(f"Starting message processing with {max_workers} workers")

    # Stats tracking
    total_processed = 0
    successful_processed = 0
    start_time = time.time()
    last_stats_time = start_time
    last_termination_check = start_time

    while not shutdown_flag:
        try:
            # Periodically check for spot termination (every 30 seconds)
            current_time = time.time()
            if current_time - last_termination_check > 30:
                if check_spot_termination():
                    logger.info("Spot termination notice received, shutting down gracefully")
                    shutdown_flag = True
                    break
                last_termination_check = current_time
                
            # Receive messages from SQS
            messages = await sqs_service.receive_messages(max_messages=batch_size)

            if not messages:
                # No messages, wait a bit before polling again
                await asyncio.sleep(1)

                # Print periodic stats even when idle
                current_time = time.time()
                if current_time - last_stats_time > 30:  # Every 30 seconds
                    elapsed = current_time - start_time
                    logger.info(f"Stats: Processed {total_processed} messages, {successful_processed} successful "
                                f"({elapsed:.2f} seconds, {total_processed/max(1, elapsed):.2f} msgs/sec)")
                    last_stats_time = current_time

                continue

            logger.info(f"Received {len(messages)} messages from SQS")

            # Process messages in parallel
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks to the executor
                futures = []
                for message in messages:
                    future = executor.submit(
                        process_single_message,
                        message,
                        region,
                        aws_access_key_id,
                        aws_secret_access_key
                    )
                    futures.append((future, message))

                # Process results as they complete
                for future, message in futures:
                    try:
                        result = future.result(timeout=120)  # 2-minute timeout
                        total_processed += 1

                        if result.success:
                            # Delete message from queue on success
                            successful_processed += 1
                            logger.info(
                                f"Successfully processed job {result.job_id}")
                            await sqs_service.delete_message(result.receipt_handle)
                        else:
                            # Log error but don't delete - it will retry automatically
                            logger.error(
                                f"Processing failed for job {result.job_id}: {result.error_message}")

                    except Exception as e:
                        total_processed += 1
                        logger.error(
                            f"Error waiting for task result: {str(e)}")

            # Print stats after each batch
            current_time = time.time()
            elapsed = current_time - start_time
            logger.info(f"Stats: Processed {total_processed} messages, {successful_processed} successful "
                        f"({elapsed:.2f} seconds, {total_processed/max(1, elapsed):.2f} msgs/sec)")
            last_stats_time = current_time

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(
                f"Error in message processing loop: {str(e)}\n{error_details}")
            # If there's an error in the main loop, wait a bit before retrying
            await asyncio.sleep(5)

        # Check for shutdown flag after each batch
        if shutdown_flag:
            logger.info("Shutdown flag detected, stopping message processing")
            break


async def main():
    """Main entry point for the worker."""
    configure_logging()
    setup_termination_handler()

    # Initialize AWS environment
    init_aws_environment()

    # Print startup banner
    logger.info("=" * 40)
    logger.info("Starting SQS indexing consumer worker")
    logger.info(f"Queue: {settings.SQS_QUEUE_NAME}")
    logger.info(f"Region: {settings.AWS_REGION}")
    logger.info(f"S3 Bucket: {settings.AWS_S3_BUCKET}")
    logger.info(f"Available CPUs: {cpu_count()}")
    logger.info("=" * 40)

    # Initialize container and services
    try:
        # Initialize container
        # Pass None since we don't have a FastAPI app here
        await container.initialize(None)

        logger.info("Successfully initialized services")

        # Process messages until shutdown
        await process_messages(
            sqs_service=container.sqs_service,
            region=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            batch_size=settings.SQS_MAX_MESSAGES,
            max_workers=None  # Use default (CPU count - 1)
        )
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(
            f"Error in main processing loop: {str(e)}\n{error_details}")
    finally:
        logger.info("Shutting down worker")
        if 'container' in globals():
            await container.cleanup()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
