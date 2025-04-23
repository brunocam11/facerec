"""
Ray task functions for face recognition processing.
"""
import gc
import logging
import time
import uuid
import asyncio
import os
from typing import Any, Dict

import psutil
import ray

from app.core.exceptions import NoFaceDetectedError
from app.services import InsightFaceRecognitionService

logger = logging.getLogger(__name__)

# Global cache for face service to reuse across tasks on the same worker process
_FACE_SERVICE_CACHE = None


@ray.remote
def process_face_image(vector_store_actor, collection_id: str,
                         image_key: str, image_bytes: bytes, max_faces: int) -> Dict[str, Any]:
    """Process a single image with face recognition as a Ray task.

    Args:
        vector_store_actor: Ray actor for vector store operations
        collection_id: ID of the face collection
        image_key: Full S3 object key of the image being processed
        image_bytes: Raw image bytes
        max_faces: Maximum number of faces to detect

    Returns:
        Dict with:
          - face_ids: List of face IDs detected in the image
          - has_faces: Boolean indicating if faces were detected
          - error: Optional error message
          - face_count: Number of faces detected
          - processing_time: Time taken to process in seconds
    """
    try:
        start_time = time.time()

        # Get task resource utilization info for logging
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=0.1)
        mem_info = process.memory_info()

        # Use basename for logging image identifier
        image_filename = os.path.basename(image_key)
        logger.info(f"Task for image {image_filename} starting "
                    f"(process CPU util: {cpu_percent:.1f}%, memory: {mem_info.rss / (1024 * 1024):.1f} MB)")

        # Initialize face service inside the task, using global cache if available
        global _FACE_SERVICE_CACHE
        if _FACE_SERVICE_CACHE is None:
            logger.debug(
                f"Initializing face service for worker process (first time)")
            _FACE_SERVICE_CACHE = InsightFaceRecognitionService()

        face_service = _FACE_SERVICE_CACHE
        logger.debug(f"Face service ready for image {image_filename}")

        # Helper function for running async code in the synchronous Ray task
        async def detect_faces_async():
            # Detect faces and extract embeddings
            return await face_service.detect_faces(
                image_bytes=image_bytes,
                max_faces=max_faces
            )

        # Run the async function using asyncio.run
        detection_result = asyncio.run(detect_faces_async())

        if not detection_result.faces:
            logger.info(f"No faces detected in image {image_filename}")
            # Run garbage collection to free memory
            gc.collect()

            processing_time = time.time() - start_time
            return {
                "face_ids": [],
                "has_faces": False,
                "error": None,
                "face_count": 0,
                "processing_time": processing_time
            }

        # Generate a unique ID for this detection operation
        detection_id = str(uuid.uuid4())
        face_ids = []

        # Log detection info
        face_count = len(detection_result.faces)
        logger.info(
            f"Detected {face_count} faces in image {image_filename}")

        # Process each detected face
        for face in detection_result.faces:
            # Generate a unique ID for this face
            face_id = str(uuid.uuid4())
            face_ids.append(face_id)

            # Convert face to dictionary for serialization
            face_dict = {
                "bounding_box": {
                    "left": face.bounding_box.left,
                    "top": face.bounding_box.top,
                    "width": face.bounding_box.width,
                    "height": face.bounding_box.height
                },
                "confidence": face.confidence,
                "embedding": face.embedding.tolist() if face.embedding is not None else None
            }

            # Store the face embedding in Pinecone using the vector store actor
            # Ray actors' methods return futures, we don't use await here
            vector_store_actor.store_face.remote(
                face_dict, collection_id, image_key, face_id, detection_id
            )

        # Release memory for detection result
        del detection_result

        # Get final resource utilization
        final_cpu_percent = process.cpu_percent(interval=0.1)
        final_mem_info = process.memory_info()

        # Run garbage collection to free memory
        gc.collect()

        processing_time = time.time() - start_time

        logger.info(f"Completed processing image {image_filename} "
                    f"(final process CPU: {final_cpu_percent:.1f}%, memory: {final_mem_info.rss / (1024 * 1024):.1f} MB) "
                    f"in {processing_time:.2f}s")

        return {
            "face_ids": face_ids,
            "has_faces": len(face_ids) > 0,
            "error": None,
            "face_count": face_count,
            "processing_time": processing_time
        }

    except NoFaceDetectedError:
        # Handle this as a legitimate result, not an error
        processing_time = time.time() - start_time
        return {
            "face_ids": [],
            "has_faces": False,
            "error": None,
            "face_count": 0,
            "processing_time": processing_time
        }
    except Exception as e:
        # Re-raise other exceptions to be handled by the caller
        image_filename = os.path.basename(image_key)
        logger.error(
            f"Error in Ray task while processing image {image_filename}: {str(e)}")
        raise
