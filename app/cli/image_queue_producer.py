#!/usr/bin/env python
"""
CLI script to load test the indexing system by queueing images from S3.

This script iterates through album folders in S3 and enqueues images for processing
until the specified number of images have been queued.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from typing import List, Optional, Tuple

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, project_root)

from app.core.config import settings
from app.core.container import ServiceContainer
from app.services.aws.s3 import S3Service
from app.services.aws.sqs import SQSService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("producer.log")
    ]
)
logger = logging.getLogger(__name__)


async def queue_images_from_albums(
    s3_service: S3Service,
    sqs_service: SQSService,
    max_images: Optional[int] = None,
    specific_album_id: Optional[str] = None,
) -> int:
    """
    Queue images from S3 albums for testing the face recognition pipeline.

    This script is intended for testing purposes only. It queues images from S3
    to SQS for processing by the face recognition worker.

    Args:
        s3_service: S3 service instance for accessing image storage
        sqs_service: SQS service instance for queueing messages
        max_images: Maximum number of images to queue. If not provided and specific_album_id
                   is provided, all images from that album will be queued.
        specific_album_id: Optional specific album ID to process. If provided,
                         only images from this album will be queued.

    Returns:
        int: Number of images queued

    Raises:
        ValueError: If the specified album is not found or has no images
    """
    queued_count = 0
    start_time = time.time()

    # Ensure services are initialized
    await s3_service.initialize()
    await sqs_service.initialize()

    if specific_album_id:
        logger.info(f"Checking album: {specific_album_id}")
        try:
            # Try to list objects with the album ID as prefix
            objects = await s3_service.list_objects(prefix=f"{specific_album_id}/")
            image_keys = [
                obj['key'] for obj in objects
                if obj['key'].lower().endswith(('.jpg', '.jpeg', '.png'))
            ]

            if not image_keys:
                raise ValueError(
                    f"No images found in album: {specific_album_id}")

            logger.info(
                f"Found {len(image_keys)} images in album: {specific_album_id}")

            # Process all images
            for image_key in image_keys:
                if max_images and queued_count >= max_images:
                    break

                await queue_single_image(
                    sqs_service, image_key, specific_album_id, s3_service.bucket_name
                )
                queued_count += 1

                # Log progress less frequently for large numbers
                if queued_count % 50 == 0 or (max_images and queued_count == max_images):
                    log_progress(queued_count, max_images, start_time)

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(
                f"Error processing album {specific_album_id}: {str(e)}\n{error_details}")
            raise ValueError(
                f"Failed to process album {specific_album_id}: {str(e)}")
    else:
        if max_images is None:
            raise ValueError(
                "max_images must be specified when processing all albums")

        # List albums for processing all
        logger.info(f"Listing albums in S3 bucket: {s3_service.bucket_name}")
        albums = await s3_service.list_albums()
        logger.info(f"Found {len(albums)} albums to process")

        # Process albums until we reach the target count
        for album in albums:
            if max_images and queued_count >= max_images:
                break

            logger.info(f"Processing album: {album}")

            try:
                objects = await s3_service.list_objects(prefix=f"{album}/")
                image_keys = [
                    obj['key'] for obj in objects
                    if obj['key'].lower().endswith(('.jpg', '.jpeg', '.png'))
                ]

                if not image_keys:
                    logger.info(f"No images found in album: {album}")
                    continue

                logger.info(
                    f"Found {len(image_keys)} images in album: {album}")

                # Process all images
                for image_key in image_keys:
                    if max_images and queued_count >= max_images:
                        break

                    await queue_single_image(
                        sqs_service, image_key, album, s3_service.bucket_name
                    )
                    queued_count += 1

                    # Log progress less frequently for large numbers
                    if queued_count % 50 == 0 or (max_images and queued_count == max_images):
                        log_progress(queued_count, max_images, start_time)

            except Exception as e:
                error_details = traceback.format_exc()
                logger.error(
                    f"Error processing album {album}: {str(e)}\n{error_details}")
                continue

    total_time = time.time() - start_time
    logger.info(
        f"Finished queueing {queued_count} images for processing in {total_time:.2f} seconds")

    if queued_count > 0:
        rate = queued_count / total_time
        logger.info(f"Average queueing rate: {rate:.2f} images/second")

    return queued_count


async def queue_single_image(
    sqs_service: SQSService,
    image_key: str,
    album: str,
    bucket_name: str
) -> None:
    """
    Queue a single image for face recognition processing.

    Args:
        sqs_service: SQS service instance
        image_key: S3 key of the image to process
        album: Album ID containing the image
        bucket_name: S3 bucket name containing the image
    """
    image_id = os.path.basename(image_key)
    collection_id = os.path.basename(album)

    message_body = {
        "image_id": image_id,
        "collection_id": collection_id,
        "s3_bucket": bucket_name,
        "s3_key": image_key,
        "max_faces": settings.MAX_FACES_PER_IMAGE
    }

    await sqs_service.send_message(message_body)


def log_progress(queued_count: int, max_images: Optional[int], start_time: float) -> None:
    """
    Log progress information during image queueing.

    Args:
        queued_count: Number of images queued so far
        max_images: Maximum number of images to queue (if specified)
        start_time: Start time of the process
    """
    elapsed = time.time() - start_time
    rate = queued_count / elapsed if elapsed > 0 else 0
    if max_images:
        logger.info(f"Progress: {queued_count}/{max_images} images queued "
                    f"({queued_count/max_images*100:.1f}%) at {rate:.1f} img/sec")
    else:
        logger.info(
            f"Progress: {queued_count} images queued at {rate:.1f} img/sec")


async def main():
    """
    Main entry point for the image queue producer script.

    This script is used for testing the face recognition pipeline by queueing
    images from S3 to SQS for processing.
    """
    parser = argparse.ArgumentParser(
        description='Queue images from S3 for face recognition testing')
    parser.add_argument('--max-images', type=int,
                        help='Maximum number of images to queue')
    parser.add_argument('--album-id', type=str,
                        help='Specific album ID to process')

    args = parser.parse_args()

    if args.max_images is not None and args.max_images <= 0:
        logger.error("max_images must be greater than zero")
        return 1

    # Show startup information
    logger.info("=" * 40)
    logger.info("Starting image queue producer (testing mode)")
    logger.info(f"Queue: {settings.SQS_QUEUE_NAME}")
    if args.max_images:
        logger.info(f"Maximum images to queue: {args.max_images}")
    if args.album_id:
        logger.info(f"Processing specific album: {args.album_id}")
    logger.info("=" * 40)

    # Initialize container and services
    container = ServiceContainer()
    await container.initialize()

    try:
        start_time = time.time()

        # Queue images
        queued_count = await queue_images_from_albums(
            s3_service=container.s3_service,
            sqs_service=container.sqs_service,
            max_images=args.max_images,
            specific_album_id=args.album_id
        )

        elapsed = time.time() - start_time

        # Print summary
        logger.info("=" * 40)
        logger.info(f"Summary:")
        logger.info(f"  Total images queued: {queued_count}")
        logger.info(f"  Total time: {elapsed:.2f} seconds")
        logger.info(
            f"  Average rate: {queued_count / elapsed:.2f} images/second")
        logger.info("=" * 40)

        return 0

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error in producer script: {str(e)}\n{error_details}")
        return 1

    finally:
        await container.cleanup()


if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
