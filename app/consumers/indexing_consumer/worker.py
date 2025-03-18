"""
Worker script for consuming and processing facial recognition indexing tasks using Ray.
"""
import os
import time
import asyncio
import logging
import traceback
import requests
import json
import ray
import gc
import psutil
import sys
import signal
from typing import List, Dict, Any, Optional, Tuple

from app.services import face_indexing
from app.services.aws.s3 import S3Service
from app.core.container import container
from app.core.exceptions import NoFaceDetectedError
from app.infrastructure.vectordb import PineconeVectorStore
from app.core.config import settings
from app.consumers.indexing_consumer.vector_store_actor import PineconeVectorStoreActor
from app.consumers.indexing_consumer.processing_tasks import process_face_image
from app.core.utils.image import bytes_to_numpy_array

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


def log_system_resources() -> Dict[str, Any]:
    """Log current system resource utilization.
    
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
        "process_cpu_percent": process.cpu_percent(interval=0.1)
    }
    
    logger.info(
        f"System resources - CPU: {metrics['avg_cpu_percent']:.1f}% "
        f"(per core: {[f'{p:.1f}%' for p in cpu_percent]}), "
        f"Memory: {metrics['memory_percent']:.1f}% used, "
        f"{metrics['memory_available_mb']:.0f}MB available, "
        f"Worker process: {metrics['process_memory_mb']:.1f}MB, "
        f"CPU: {metrics['process_cpu_percent']:.1f}%"
    )
    
    return metrics


async def download_s3_image(s3_service: S3Service, bucket: str, key: str, local_path: str) -> bool:
    """Download an image from S3 to a local path using the S3Service.
    
    Args:
        s3_service: S3Service instance
        bucket: S3 bucket name
        key: S3 object key
        local_path: Local file path to save the image
        
    Returns:
        bool: True if download successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        logger.debug(f"Downloading S3 image {bucket}/{key} to {local_path}")
        
        # Check and update bucket if needed
        original_bucket = None
        if s3_service.bucket_name != bucket:
            original_bucket = s3_service.bucket_name
            s3_service.bucket_name = bucket
            # Need to re-initialize with the new bucket
            await s3_service.initialize()
        
        # Ensure S3 client is initialized
        if not s3_service.initialized:
            await s3_service.initialize()
            
        # Use the proper S3Service method to download
        # We'll use get_object since there's no direct download method
        response = s3_service.s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
            
        # Write to local file
        with open(local_path, 'wb') as f:
            f.write(content)
            
        # Restore original bucket if we changed it
        if original_bucket:
            s3_service.bucket_name = original_bucket
            await s3_service.initialize()
            
        return True
    except Exception as e:
        logger.error(f"Failed to download from S3 {bucket}/{key}: {str(e)}")
        return False


def configure_environment():
    """Configure environment variables for optimal ML performance."""
    # Set environment variables to ensure all CPUs are utilized by ML operations
    cpu_count = os.cpu_count()
    os.environ['OMP_NUM_THREADS'] = str(cpu_count)
    logger.info(f"Set OMP_NUM_THREADS to {cpu_count} to maximize CPU utilization")
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
        raise RuntimeError("Ray must be initialized before calling initialize_services")
    
    # For vector store, use an actor to avoid serialization issues
    logger.info("Creating vector store actor")
    vector_store_actor = PineconeVectorStoreActor.remote()
    
    # Log resource usage after initialization
    log_system_resources()
    
    logger.info("Services initialized and ready for processing")
    
    return s3_service, vector_store_actor


async def process_messages(sqs_service, region: str, batch_size: int = 10) -> None:
    """Process messages from the SQS queue using Ray tasks for parallel processing.
    
    Args:
        sqs_service: SQS service client
        region: AWS region
        batch_size: Number of messages to process in each batch
    """
    global shutdown_flag
    global in_progress_tasks
    
    logger.info(f"Starting message processing with Ray in {settings.ENVIRONMENT} environment")
    logger.info(f"Scale-to-zero enabled: worker will exit after {IDLE_TIMEOUT_SECONDS}s of inactivity")
    
    # Ensure Ray is initialized - this should already be done in main.py
    if not ray.is_initialized():
        logger.warning("Ray was not initialized in main.py, initializing now...")
        ray.init(ignore_reinit_error=True)
        logger.info("Ray initialized in worker")
    else:
        logger.info("Using existing Ray instance")
    
    # Get dynamically allocated CPU count
    cpu_count = ray.available_resources().get('CPU', 0)
    logger.info(f"Ray allocated {cpu_count} CPUs for processing")
    
    # Set environment variables for optimal ML performance
    os.environ['OMP_NUM_THREADS'] = str(max(1, int(cpu_count)))
    
    # Initialize required services 
    s3_service, vector_store_actor = await initialize_services(region)
    
    # Get Ray cluster resources
    ray_resources = ray.available_resources()
    logger.info(f"Ray cluster resources: {ray_resources}")
    logger.info(f"System has {cpu_count} available CPUs for parallel processing")
    
    # Stats tracking
    total_processed = 0
    successful_processed = 0
    images_with_faces = 0
    images_no_faces = 0
    error_count = 0
    total_processing_time = 0
    start_time = time.time()
    last_stats_time = start_time
    last_termination_check = start_time
    last_resource_check = start_time
    last_message_time = start_time  # Track time of last received message for idle shutdown
    idle_shutdown_attempts = 0  # Track how many times we've tried to shut down due to idle
    
    # Log idle timeout configuration
    logger.info(f"Worker configured to shut down after {IDLE_TIMEOUT_SECONDS} seconds of inactivity")

    async def process_single_message_async(message):
        """Process a single message using Ray tasks.
        
        Args:
            message: SQS message to process
            
        Returns:
            Tuple: (success, job_id, receipt_handle, face_ids or error message, has_faces)
        """
        global in_progress_tasks
        
        # Increment in-progress tasks counter
        in_progress_tasks += 1
        
        # Declare variables from outer scope that will be modified
        nonlocal images_with_faces
        nonlocal images_no_faces
        nonlocal successful_processed
        nonlocal total_processing_time
        
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

            logger.info(f"Processing job {job_id}: image {image_id} for collection {collection_id}")

            # Download image from S3 to a temporary location using async S3 service
            temp_dir = f"/tmp/facerec/{job_id}"
            os.makedirs(temp_dir, exist_ok=True)
            local_image_path = f"{temp_dir}/{os.path.basename(image_id)}"

            # Download image asynchronously
            success = await download_s3_image(s3_service, s3_bucket, s3_key, local_image_path)
            if not success:
                raise RuntimeError(f"Failed to download image from S3: {s3_bucket}/{s3_key}")

            try:
                # Read image into memory
                with open(local_image_path, 'rb') as img_file:
                    image_bytes = img_file.read()
                    
                    # Submit Ray task for face processing
                    try:
                        # Use asyncio.to_thread to avoid blocking the event loop while waiting
                        # for Ray task to complete
                        result = await asyncio.to_thread(
                            lambda: ray.get(
                                process_face_image.remote(
                                    vector_store_actor,
                                    collection_id, 
                                    image_id, 
                                    image_bytes, 
                                    max_faces
                                )
                            )
                        )
                        
                        face_count = result['face_count']
                        processing_time = result['processing_time']
                        
                        # Record stats and log results
                        if face_count > 0:
                            logger.info(
                                f"Successfully processed {image_id}: found {face_count} faces "
                                f"in {processing_time:.2f}s"
                            )
                            images_with_faces += 1
                        else:
                            logger.info(f"No faces detected in image {image_id}")
                            images_no_faces += 1
                            
                        # Update processing time stats
                        total_processing_time += processing_time
                        successful_processed += 1
                            
                        # Update job state (would typically use a DB, but for now just log)
                        logger.info(
                            f"Job {job_id} progress: processed image {image_id} with {face_count} faces, "
                            f"collection_id={collection_id}"
                        )
                        
                        return True, job_id, receipt_handle, face_count, True
                    except ray.exceptions.RayTaskError as e:
                        # Handle unexpected Ray task errors
                        raise e
            finally:
                # Clean up temporary files and run garbage collection
                try:
                    if os.path.exists(local_image_path):
                        os.remove(local_image_path)
                    if os.path.exists(temp_dir) and len(os.listdir(temp_dir)) == 0:
                        os.rmdir(temp_dir)
                    # Force garbage collection after processing
                    gc.collect()
                except Exception as e:
                    logger.warning(f"Failed to clean up temp files: {str(e)}")
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing job {job_id}: {str(e)}\n{error_details}")
            return False, job_id, receipt_handle, str(e), False
        finally:
            # Decrement in-progress tasks counter
            in_progress_tasks -= 1

    try:
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
                    
                # Periodically check system resources (every 30 seconds)
                if current_time - last_resource_check > 30:
                    log_system_resources()
                    last_resource_check = current_time
                    
                # Check for idle timeout (worker has been idle for too long)
                idle_time = current_time - last_message_time
                if idle_time > IDLE_TIMEOUT_SECONDS:
                    # Check if there are any in-progress tasks
                    if in_progress_tasks > 0:
                        logger.info(f"Worker idle for {idle_time:.1f}s but {in_progress_tasks} tasks still in progress, delaying shutdown")
                        # Continue processing
                        idle_shutdown_attempts += 1
                        # If tasks are stuck for too long, force shutdown
                        if idle_shutdown_attempts > 5:  # After 5 attempts (at least 5 seconds apart)
                            logger.warning(f"Forcing shutdown after {idle_shutdown_attempts} attempts with tasks stuck in progress")
                            sys.exit(0)
                    else:
                        # Check SQS one last time to make sure there are no messages
                        # before shutting down
                        final_check_messages = await sqs_service.receive_messages(max_messages=1)
                        if not final_check_messages:
                            logger.info(f"Worker has been idle for {idle_time:.1f} seconds (> {IDLE_TIMEOUT_SECONDS}s), shutting down to enable scale-to-zero")
                            logger.info("Shutdown will trigger ASG scale-in via ECS-FaceRec-NoRunningTasks alarm")
                            # Exit with success code
                            sys.exit(0)
                        else:
                            # Found a message, reset the idle timer
                            logger.info("Found new messages during idle timeout check, continuing")
                            last_message_time = current_time
                            idle_shutdown_attempts = 0
                    
                # Receive messages from SQS
                messages = await sqs_service.receive_messages(max_messages=batch_size)

                if not messages:
                    # No messages, wait a bit before polling again
                    await asyncio.sleep(1)
                    continue
                
                # Reset idle timer when messages are received
                last_message_time = current_time
                idle_shutdown_attempts = 0

                logger.info(f"Received {len(messages)} messages from SQS")

                # Process messages concurrently using asyncio tasks
                # Each task will use a Ray task for the CPU-intensive part
                tasks = []
                for message in messages:
                    # Create task for this message
                    task = asyncio.create_task(
                        process_single_message_async(message)
                    )
                    tasks.append(task)
                    
                # Process results as they complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Task raised exception: {str(result)}")
                        total_processed += 1
                        error_count += 1
                        continue
                        
                    success, job_id, receipt_handle, face_count, has_faces = result
                    total_processed += 1
                    
                    if success:
                        # Delete message from queue on success
                        successful_processed += 1
                        
                        # Track images with/without faces
                        if has_faces:
                            images_with_faces += 1
                        else:
                            images_no_faces += 1
                            
                        logger.info(f"Successfully processed job {job_id}")
                        await sqs_service.delete_message(receipt_handle)
                    else:
                        # Log error but don't delete - it will retry automatically
                        logger.error(f"Processing failed for job {job_id}: {face_count}")
                        error_count += 1

                # Log stats every 60 seconds
                if current_time - last_stats_time > 60:
                    elapsed = current_time - start_time
                    avg_time = total_processing_time / successful_processed if successful_processed > 0 else 0
                    logger.info(
                        f"Stats: Processed {total_processed} messages, {successful_processed} successful ({elapsed:.2f} seconds)"
                    )
                    logger.info(
                        f"Face statistics: {images_with_faces} images with faces, {images_no_faces} images with no faces, {error_count} errors"
                    )
                    logger.info(
                        f"Performance: Avg processing time per image: {avg_time:.2f}s, Total processing time: {total_processing_time:.2f}s"
                    )
                    # Also log current idle time and active tasks
                    logger.info(f"Worker state: idle time={idle_time:.1f}s (shutdown after {IDLE_TIMEOUT_SECONDS}s), active tasks={in_progress_tasks}")
                    last_stats_time = current_time
                        
            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
                # If there's an error in the main loop, wait a bit before retrying
                await asyncio.sleep(5)
    finally:
        # Clean up resources
        try:
            logger.info("Shutting down worker gracefully...")
            
            # Wait for in-progress tasks to complete (with a timeout)
            if in_progress_tasks > 0:
                logger.info(f"Waiting for {in_progress_tasks} tasks to complete...")
                wait_time = 0
                max_wait_time = 30  # Maximum seconds to wait for in-progress tasks
                while in_progress_tasks > 0 and wait_time < max_wait_time:
                    await asyncio.sleep(1)
                    wait_time += 1
                
                if in_progress_tasks > 0:
                    logger.warning(f"Forcing shutdown with {in_progress_tasks} tasks still in progress after waiting {wait_time}s")
            
            # Clean up S3 service
            await s3_service.cleanup()
            logger.info("S3 service cleaned up")
            
            # Terminate Ray on shutdown
            if ray.is_initialized():
                logger.info("Shutting down Ray...")
                ray.shutdown()
                logger.info("Ray shutdown complete")
                
            logger.info("Worker shutdown complete - goodbye!")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
