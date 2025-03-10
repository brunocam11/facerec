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
from typing import List, Dict, Any, Optional, Tuple
import gc

from app.services import face_indexing
from app.services.aws.s3 import S3Service
from app.core.container import container
from app.core.exceptions import NoFaceDetectedError

# Configure logging
logger = logging.getLogger(__name__)

# Global flag for signaling shutdown
shutdown_flag = False


def set_shutdown_flag():
    """Set the shutdown flag to signal worker processes to stop."""
    global shutdown_flag
    shutdown_flag = True
    logger.info("Shutdown flag set, workers will terminate after current batch")


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


@ray.remote
class FaceProcessorActor:
    """Ray actor that holds a single instance of the face recognition model.

    This actor will be instantiated once per CPU core, allowing efficient
    parallel processing without duplicating the model in memory.
    """

    def __init__(self):
        """Initialize the face recognition service once per actor."""
        from app.services import InsightFaceRecognitionService
        from app.infrastructure.vectordb import PineconeVectorStore
        
        # Log that we're initializing a new model instance
        actor_id = ray.get_runtime_context().get_actor_id()
        logger.info(f"Initializing face recognition model for Ray actor {actor_id}")
        
        # Create service instances
        self.face_service = InsightFaceRecognitionService()
        self.vector_store = PineconeVectorStore()
        self.indexing_service = face_indexing.FaceIndexingService(
            face_service=self.face_service,
            vector_store=self.vector_store
        )
        logger.info(f"Model initialization complete for Ray actor {actor_id}")
    
    def process_image(self, 
                     collection_id: str, 
                     image_id: str, 
                     image_bytes: bytes, 
                     max_faces: int) -> Dict[str, Any]:
        """Process a single image with the face recognition model.
        
        Args:
            collection_id: ID of the face collection
            image_id: ID of the image being processed
            image_bytes: Raw image bytes
            max_faces: Maximum number of faces to detect
            
        Returns:
            Dict with:
              - face_ids: List of face IDs detected in the image
              - has_faces: Boolean indicating if faces were detected
              - error: Optional error message
            
        Raises:
            Exception: For any processing error except NoFaceDetectedError
        """
        # This runs in a separate process managed by Ray
        try:
            # Use the async method with a synchronous wrapper since we're in a separate process
            import asyncio
            
            # Process the image - using the correct method name (index_faces, not index_faces_sync)
            indexing_result = asyncio.run(self.indexing_service.index_faces(
                collection_id=collection_id,
                image_id=image_id,
                image_bytes=image_bytes,
                max_faces=max_faces
            ))
            
            # Extract face IDs from result
            face_ids = [face.face_id for face in indexing_result.face_records]
            return {
                "face_ids": face_ids,
                "has_faces": len(face_ids) > 0, 
                "error": None
            }
            
        except NoFaceDetectedError:
            # Handle this as a legitimate result, not an error
            return {
                "face_ids": [],
                "has_faces": False,
                "error": None
            }
        except Exception as e:
            # Re-raise other exceptions to be handled by the caller
            logger.error(f"Error in Ray actor while processing image {image_id}: {str(e)}")
            raise


async def process_messages(sqs_service, region: str, batch_size: int = 10) -> None:
    """Process messages from the SQS queue using Ray actors for parallel processing.
    
    Args:
        sqs_service: SQS service client
        region: AWS region
        batch_size: Number of messages to process in each batch
    """
    global shutdown_flag
    
    logger.info("Starting message processing with Ray actors")
    
    # Ensure Ray is initialized
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
        logger.info("Ray initialized")
    
    # Initialize S3 service for async downloads
    s3_service = S3Service(region_name=region)
    await s3_service.initialize()
    logger.info("S3 service initialized for async downloads")
    
    # Use only 1 actor to avoid memory issues
    # This will allow the single actor to use all available memory
    num_actors = 1
    logger.info("Memory optimization: Using single actor configuration to reduce memory usage")
    
    logger.info(f"Creating {num_actors} Ray actors for face processing")
    face_processors = [FaceProcessorActor.remote() for _ in range(num_actors)]
    logger.info(f"Ray actors created: {len(face_processors)}")
    
    # Stats tracking
    total_processed = 0
    successful_processed = 0
    images_with_faces = 0
    images_no_faces = 0
    error_count = 0
    start_time = time.time()
    last_stats_time = start_time
    last_termination_check = start_time
    message_counter = 0

    async def process_single_message_async(message, actor_index: int):
        """Process a single message using a Ray actor.
        
        Args:
            message: SQS message to process
            actor_index: Index of the Ray actor to use
            
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
                # Process the image using Ray actor
                with open(local_image_path, 'rb') as img_file:
                    image_bytes = img_file.read()
                    
                    # Get the assigned Ray actor
                    actor = face_processors[actor_index]
                    
                    # Call the Ray actor and wait for the result
                    # We use asyncio.to_thread to avoid blocking the event loop
                    try:
                        result = await asyncio.to_thread(
                            lambda: ray.get(
                                actor.process_image.remote(
                                    collection_id, 
                                    image_id, 
                                    image_bytes, 
                                    max_faces
                                )
                            )
                        )
                        
                        face_ids = result["face_ids"]
                        has_faces = result["has_faces"]
                        
                        if has_faces:
                            logger.info(f"Successfully processed job {job_id}: found {len(face_ids)} faces")
                        else:
                            logger.info(f"Successfully processed job {job_id}: no faces detected")
                            
                        return True, job_id, receipt_handle, face_ids, has_faces
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
                    
                # Receive messages from SQS
                messages = await sqs_service.receive_messages(max_messages=batch_size)

                if not messages:
                    # No messages, wait a bit before polling again
                    await asyncio.sleep(1)
                    continue

                logger.info(f"Received {len(messages)} messages from SQS")

                # Process messages concurrently using asyncio tasks
                # Each task will use a Ray actor for the CPU-intensive part
                tasks = []
                for i, message in enumerate(messages):
                    # Distribute messages across actors using round-robin
                    actor_index = message_counter % len(face_processors)
                    message_counter += 1
                    
                    # Create task for this message
                    task = asyncio.create_task(
                        process_single_message_async(message, actor_index)
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
                        
                    success, job_id, receipt_handle, face_ids_or_error, has_faces = result
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
                        logger.error(f"Processing failed for job {job_id}: {face_ids_or_error}")
                        error_count += 1

                # Print stats after each batch
                current_time = time.time()
                if current_time - last_stats_time > 30:  # Every 30 seconds
                    elapsed = current_time - start_time
                    logger.info(f"Stats: Processed {total_processed} messages, {successful_processed} successful "
                                f"({elapsed:.2f} seconds)")
                    logger.info(f"Face statistics: {images_with_faces} images with faces, "
                                f"{images_no_faces} images with no faces, {error_count} errors")
                    last_stats_time = current_time
                        
            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
                # If there's an error in the main loop, wait a bit before retrying
                await asyncio.sleep(5)
    finally:
        # Clean up resources
        try:
            # Clean up S3 service
            await s3_service.cleanup()
            logger.info("S3 service cleaned up")
            
            # Terminate Ray on shutdown
            if ray.is_initialized():
                logger.info("Shutting down Ray...")
                ray.shutdown()
                logger.info("Ray shutdown complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
