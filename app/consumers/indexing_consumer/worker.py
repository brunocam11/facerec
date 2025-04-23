"""
Worker script for consuming and processing facial recognition indexing tasks using Ray.
"""
import asyncio
import gc
import logging
import os
import signal
import time
import traceback
from typing import Any, Dict, Tuple

import psutil
import ray
import requests

from app.consumers.indexing_consumer.processing_tasks import process_face_image
from app.consumers.indexing_consumer.vector_store_actor import PineconeVectorStoreActor
from app.core.config import settings
from app.services.aws.s3 import S3Service
from app.services.aws.s3 import StorageError

# Configure logging
logger = logging.getLogger(__name__)

# Global flag for signaling shutdown
shutdown_flag = False

# Track in-progress tasks
in_progress_tasks = 0

# Get idle timeout directly from settings
# Default is 120 seconds (2 minutes) based on the SQS-FaceRec-QueueEmpty alarm (3 minutes)
IDLE_TIMEOUT_SECONDS = settings.WORKER_IDLE_TIMEOUT


def set_shutdown_flag():
    """Set the shutdown flag to signal worker processes to stop."""
    global shutdown_flag
    shutdown_flag = True
    logger.info("Shutdown flag set, workers will terminate after current batch")


def handle_sigterm(signum, frame):
    """Handle SIGTERM signal by gracefully shutting down."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    set_shutdown_flag()


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def check_spot_termination() -> bool:
    """Check if EC2 spot instance termination is imminent.

    Returns:
        bool: True if spot termination notice detected, False otherwise
    """
    try:
        # AWS provides a specific endpoint for spot instances to check termination notices
        # This endpoint is only accessible from within the EC2 instance
        response = requests.get(
            "http://169.254.169.254/latest/meta-data/spot/instance-action",
            timeout=2
        )
        # If we get a 200 response, termination is imminent
        return response.status_code == 200
    except Exception:
        # If there's any error (including connection timeout), assume no termination
        return False


def log_system_resources(context: str = "") -> Dict[str, Any]:
    """Log current system resource utilization.

    Args:
        context: Optional string to provide context for the resource log

    Returns:
        Dict containing resource utilization metrics
    """
    cpu_percent = psutil.cpu_percent(interval=0.5, percpu=True)
    memory = psutil.virtual_memory()
    process = psutil.Process()
    process_memory = process.memory_info()

    metrics = {
        "cpu_percent_per_core": cpu_percent,
        "avg_cpu_percent": sum(cpu_percent) / len(cpu_percent),
        "memory_percent": memory.percent,
        "memory_available_mb": memory.available / (1024 * 1024),
        "process_memory_mb": process_memory.rss / (1024 * 1024),
        "process_cpu_percent": process.cpu_percent(interval=0.1),
        "context": context
    }

    prefix = f"[{context}] " if context else ""
    logger.info(
        f"{prefix}System resources - CPU: {metrics['avg_cpu_percent']:.1f}% "
        f"(per core: {[f'{p:.1f}%' for p in cpu_percent]}), "
        f"Memory: {metrics['memory_percent']:.1f}% used, "
        f"{metrics['memory_available_mb']:.0f}MB available, "
        f"Worker process: {metrics['process_memory_mb']:.1f}MB, "
        f"CPU: {metrics['process_cpu_percent']:.1f}%"
    )

    return metrics


async def download_s3_image(s3_service: S3Service, bucket: str, key: str, local_path: str) -> bool:
    """Download an image from S3.

    Args:
        s3_service: Initialized S3Service instance.
        bucket: The S3 bucket name.
        key: The S3 object key.
        local_path: The local path to save the downloaded file.

    Returns:
        True if download was successful, False otherwise.
    """
    logger.debug(f"Downloading s3://{bucket}/{key} to {local_path}")
    try:
        # Use the new download_file method for efficient streaming
        await s3_service.download_file(bucket=bucket, key=key, file_path=local_path)

        logger.info(f"Successfully downloaded s3://{bucket}/{key}")
        return True
    except StorageError as e:
        # Catch specific StorageError from our service
        logger.error(f"S3 Storage Error downloading s3://{bucket}/{key}: {e}")
        return False
    except Exception as e:
        # Catch unexpected errors during download
        logger.error(f"Unexpected error downloading s3://{bucket}/{key}", error=str(e), exc_info=True)
        return False


def configure_environment():
    """Configure environment variables for optimal ML performance."""
    # Set environment variables to ensure all CPUs are utilized by ML operations
    cpu_count = os.cpu_count()
    os.environ['OMP_NUM_THREADS'] = str(cpu_count)
    logger.info(
        f"Set OMP_NUM_THREADS to {cpu_count} to maximize CPU utilization")
    return cpu_count


async def initialize_services(region: str):
    """Initialize required services for face recognition processing.

    Args:
        region: AWS region name

    Returns:
        Tuple of (S3Service, vector_store_actor)
    """
    # Initialize S3 service for async downloads
    s3_service = S3Service(region_name=region)
    await s3_service.initialize()
    logger.info("S3 service initialized for async downloads")

    # Verify Ray is initialized before proceeding
    if not ray.is_initialized():
        raise RuntimeError(
            "Ray must be initialized before calling initialize_services")

    # For vector store, use an actor to avoid serialization issues
    logger.info("Creating vector store actor")
    vector_store_actor = PineconeVectorStoreActor.remote()

    # Log resource usage after initialization
    log_system_resources("Service Initialization")

    logger.info("Services initialized and ready for processing")

    return s3_service, vector_store_actor


class MessageProcessor:
    """Handles SQS message processing and resource management."""

    def __init__(self, sqs_service, region: str):
        self.sqs_service = sqs_service
        self.region = region
        self.s3_service = None
        self.vector_store_actor = None

        # Stats tracking
        self.total_processed = 0
        self.successful_processed = 0
        self.images_with_faces = 0
        self.images_no_faces = 0
        self.error_count = 0
        self.total_processing_time = 0
        self.start_time = time.time()
        self.last_stats_time = self.start_time
        self.last_resource_check = self.start_time

    async def initialize(self):
        """Initialize required services."""
        # S3Service uses internal context manager, no explicit init needed here
        self.s3_service = S3Service(region_name=self.region)

        logger.info("S3 service configured")

        if not ray.is_initialized():
            raise RuntimeError(
                "Ray must be initialized before calling initialize_services")

        logger.info("Creating vector store actor")
        # Actor will initialize its own PineconeVectorStore internally
        self.vector_store_actor = PineconeVectorStoreActor.remote() # Call without args

        log_system_resources("Service Initialization")
        logger.info("Services initialized and ready for processing")

    async def cleanup(self):
        """Clean up resources."""
        try:
            log_system_resources("Shutdown")

            if ray.is_initialized():
                logger.info("Shutting down Ray...")
                ray.shutdown()
                logger.info("Ray shutdown complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    async def process_single_message(self, message: Dict[str, Any]) -> Tuple[bool, str, str, Any, bool]:
        """Process a single message using Ray tasks.

        Args:
            message: SQS message to process

        Returns:
            Tuple: (success, job_id, receipt_handle, face_ids or error message, has_faces)
        """
        # Extract message details
        receipt_handle = message['receipt_handle']
        body = message['body']
        job_id = body.get('job_id', 'unknown')

        try:
            # Extract indexing parameters
            collection_id = body.get('collection_id')
            s3_bucket = body.get('s3_bucket')
            image_key = body.get('image_key')
            max_faces = settings.MAX_FACES_PER_IMAGE

            if not all([collection_id, s3_bucket, image_key]):
                raise ValueError("Missing required parameters in message body")

            logger.info(
                f"Processing job {job_id}: image {image_key} for collection {collection_id}")

            # Download image from S3
            temp_dir = f"/tmp/facerec/{job_id}"
            os.makedirs(temp_dir, exist_ok=True)
            local_image_path = f"{temp_dir}/{job_id}-{os.path.basename(image_key)}"

            # Pass bucket and image_key directly to the download function
            success = await download_s3_image(self.s3_service, s3_bucket, image_key, local_image_path)
            if not success:
                raise RuntimeError(
                    f"Failed to download image from S3: {s3_bucket}/{image_key}")

            try:
                # Process image
                with open(local_image_path, 'rb') as img_file:
                    image_bytes = img_file.read()

                    result = await asyncio.to_thread(
                        lambda: ray.get(
                            process_face_image.remote(
                                self.vector_store_actor,
                                collection_id,
                                image_key,
                                image_bytes,
                                max_faces
                            )
                        )
                    )

                    face_count = result['face_count']
                    processing_time = result['processing_time']

                    # Update stats
                    if face_count > 0:
                        logger.info(
                            f"Successfully processed {image_key}: found {face_count} faces "
                            f"in {processing_time:.2f}s"
                        )
                        self.images_with_faces += 1
                    else:
                        logger.info(f"No faces detected in image {image_key}")
                        self.images_no_faces += 1

                    self.total_processing_time += processing_time
                    self.successful_processed += 1

                    logger.info(
                        f"Job {job_id} progress: processed image {image_key} with {face_count} faces, "
                        f"collection_id={collection_id}"
                    )

                    return True, job_id, receipt_handle, face_count, True
            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(local_image_path):
                        os.remove(local_image_path)
                    if os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == 0:
                        os.rmdir(temp_dir)
                    gc.collect()
                except Exception as e:
                    logger.warning(f"Failed to clean up temp files: {str(e)}")
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(
                f"Error processing job {job_id}: {str(e)}\n{error_details}")
            return False, job_id, receipt_handle, str(e), False

    def log_stats(self):
        """Log processing statistics."""
        current_time = time.time()
        if current_time - self.last_stats_time > 30:  # Every 30 seconds
            elapsed = current_time - self.start_time
            avg_time = self.total_processing_time / \
                self.successful_processed if self.successful_processed > 0 else 0

            logger.info(
                f"Stats: Processed {self.total_processed} messages, {self.successful_processed} successful "
                f"({elapsed:.2f} seconds, avg={avg_time:.2f}s per message)"
            )
            logger.info(
                f"Face statistics: {self.images_with_faces} images with faces, "
                f"{self.images_no_faces} images with no faces, {self.error_count} errors"
            )

            log_system_resources(
                f"Batch Stats (processed={self.total_processed})")

            self.last_stats_time = current_time
            self.last_resource_check = current_time


async def process_messages(sqs_service, region: str) -> None:
    """Process messages from the SQS queue using Ray tasks for parallel processing.

    Args:
        sqs_service: SQS service client
        region: AWS region
    """
    logger.info(
        f"Starting message processing with Ray in {settings.ENVIRONMENT} environment")

    # Initialize Ray if needed
    if not ray.is_initialized():
        logger.warning(
            "Ray was not initialized in main.py, initializing now...")
        ray.init(ignore_reinit_error=True)
        logger.info("Ray initialized in worker")
    else:
        logger.info("Using existing Ray instance")

    # Get Ray resources
    cpu_count = ray.available_resources().get('CPU', 0)
    logger.info(f"Ray allocated {cpu_count} CPUs for processing")
    os.environ['OMP_NUM_THREADS'] = str(max(1, int(cpu_count)))

    # Initialize processor
    processor = MessageProcessor(sqs_service, region)
    await processor.initialize()

    try:
        while True:
            try:
                # Receive messages
                messages = await sqs_service.receive_messages(max_messages=settings.SQS_BATCH_SIZE)
                if not messages:
                    await asyncio.sleep(1)
                    continue

                logger.info(f"Received {len(messages)} messages from SQS")

                # Process messages concurrently
                tasks = [
                    asyncio.create_task(
                        processor.process_single_message(message))
                    for message in messages
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Handle results
                for result in results:
                    processor.total_processed += 1

                    if isinstance(result, Exception):
                        logger.error(f"Task raised exception: {str(result)}")
                        processor.error_count += 1
                        continue

                    success, job_id, receipt_handle, face_count, has_faces = result
                    if success:
                        logger.info(f"Successfully processed job {job_id}")
                        # Attempt to delete and check result
                        deleted = await sqs_service.delete_message(receipt_handle)
                        if not deleted:
                            logger.warning(f"Failed to delete message for job {job_id} (receipt: {receipt_handle}). It might be processed again.")
                    else:
                        logger.error(
                            f"Processing failed for job {job_id}: {face_count}")
                        processor.error_count += 1

                # Log stats periodically
                processor.log_stats()

            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
                await asyncio.sleep(5)
    finally:
        await processor.cleanup()
