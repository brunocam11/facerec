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

# Add the parent directory to the path for module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.core.config import settings
from app.core.container import ServiceContainer


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
    s3_service, 
    sqs_service, 
    total_images: int,
    batch_size: int = 100,
    sleep_between_batches: float = 1.0,
    max_albums: Optional[int] = None,
    album_prefix: Optional[str] = None,
    dry_run: bool = False
) -> Tuple[int, List[str]]:
    """
    Queue images from S3 albums for processing.
    
    Args:
        s3_service: S3 service instance
        sqs_service: SQS service instance
        total_images: Total number of images to queue
        batch_size: Number of images to queue in a batch
        sleep_between_batches: Time to sleep between batches (seconds)
        max_albums: Maximum number of albums to process
        album_prefix: Prefix to filter albums
        dry_run: If True, don't actually queue messages
        
    Returns:
        Tuple[int, List[str]]: (Number of queued images, List of job IDs)
    """
    # Initialize counters
    queued_count = 0
    job_ids = []
    start_time = time.time()
    
    # List albums
    logger.info(f"Listing albums in S3 bucket: {s3_service.bucket_name}")
    albums = await s3_service.list_albums()
    
    if album_prefix:
        albums = [a for a in albums if a.startswith(album_prefix)]
    
    if max_albums and len(albums) > max_albums:
        logger.info(f"Limiting to {max_albums} albums out of {len(albums)} available")
        albums = albums[:max_albums]
    
    logger.info(f"Found {len(albums)} albums to process")
    
    # Process albums until we reach the target count
    for album in albums:
        if queued_count >= total_images:
            break
            
        logger.info(f"Processing album: {album}")
        
        # List images in this album
        try:
            objects = await s3_service.list_objects(prefix=f"{album}/")
            image_keys = [
                obj['key'] for obj in objects 
                if obj['key'].lower().endswith(('.jpg', '.jpeg', '.png'))
            ]
            
            if not image_keys:
                logger.info(f"No images found in album: {album}")
                continue
                
            logger.info(f"Found {len(image_keys)} images in album: {album}")
            
            # Process images in batches
            for i in range(0, len(image_keys), batch_size):
                if queued_count >= total_images:
                    break
                    
                batch = image_keys[i:i+batch_size]
                remaining = total_images - queued_count
                if len(batch) > remaining:
                    batch = batch[:remaining]
                    
                batch_start = time.time()
                logger.info(f"Queueing batch of {len(batch)} images")
                
                # Queue each image
                for image_key in batch:
                    # Create a unique image ID
                    image_id = os.path.basename(image_key)
                    collection_id = os.path.basename(album)
                    
                    message_body = {
                        "image_id": image_id,
                        "collection_id": collection_id,
                        "s3_bucket": s3_service.bucket_name,
                        "s3_key": image_key,
                        "max_faces": settings.MAX_FACES_PER_IMAGE
                    }
                    
                    if not dry_run:
                        job_id = await sqs_service.send_message(message_body)
                        job_ids.append(job_id)
                    else:
                        # In dry run mode, simulate job ID
                        job_id = f"dry-run-{queued_count}"
                        job_ids.append(job_id)
                        
                    queued_count += 1
                    
                    # Simple progress indicator
                    if queued_count % 10 == 0 or queued_count == total_images:
                        elapsed = time.time() - start_time
                        rate = queued_count / elapsed if elapsed > 0 else 0
                        logger.info(f"Progress: {queued_count}/{total_images} images queued "
                                   f"({queued_count/total_images*100:.1f}%) at {rate:.1f} img/sec")
                
                batch_time = time.time() - batch_start
                logger.info(f"Batch completed in {batch_time:.2f} seconds")
                
                # Sleep between batches to avoid overwhelming the queue
                if sleep_between_batches > 0 and not dry_run:
                    await asyncio.sleep(sleep_between_batches)
        
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"Error processing album {album}: {str(e)}\n{error_details}")
            # Continue with next album
    
    total_time = time.time() - start_time
    logger.info(f"Finished queueing {queued_count} images for processing in {total_time:.2f} seconds")
    
    if queued_count > 0:
        rate = queued_count / total_time
        logger.info(f"Average queueing rate: {rate:.2f} images/second")
    
    return queued_count, job_ids


async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Queue images from S3 for processing')
    parser.add_argument('--total', type=int, required=True, help='Total number of images to queue')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for queueing')
    parser.add_argument('--sleep', type=float, default=1.0, help='Sleep time between batches in seconds')
    parser.add_argument('--max-albums', type=int, help='Maximum number of albums to process')
    parser.add_argument('--album-prefix', type=str, help='Prefix to filter albums')
    parser.add_argument('--output', type=str, help='Output file to save job IDs')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t actually queue messages, just simulate')
    
    args = parser.parse_args()
    
    if args.total <= 0:
        logger.error("Total images must be greater than zero")
        return 1
    
    # Show startup information
    logger.info("=" * 40)
    logger.info("Starting image queue producer")
    logger.info(f"Queue: {settings.SQS_QUEUE_NAME}")
    logger.info(f"Target: {args.total} images")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Sleep between batches: {args.sleep} seconds")
    if args.album_prefix:
        logger.info(f"Album prefix: {args.album_prefix}")
    if args.max_albums:
        logger.info(f"Max albums: {args.max_albums}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No actual messages will be queued")
    logger.info("=" * 40)
        
    # Initialize container and services
    container = ServiceContainer()
    await container.initialize(None)  # Pass None since we don't have a FastAPI app here
    
    try:
        start_time = time.time()
        
        # Queue images
        queued_count, job_ids = await queue_images_from_albums(
            s3_service=container.s3_service,
            sqs_service=container.sqs_service,
            total_images=args.total,
            batch_size=args.batch_size,
            sleep_between_batches=args.sleep,
            max_albums=args.max_albums,
            album_prefix=args.album_prefix,
            dry_run=args.dry_run
        )
        
        elapsed = time.time() - start_time
        
        # Print summary
        logger.info("=" * 40)
        logger.info(f"Summary:")
        logger.info(f"  Total images queued: {queued_count}")
        logger.info(f"  Total time: {elapsed:.2f} seconds")
        logger.info(f"  Average rate: {queued_count / elapsed:.2f} images/second")
        logger.info("=" * 40)
        
        # Save job IDs if requested
        if args.output and job_ids:
            with open(args.output, 'w') as f:
                json.dump(job_ids, f, indent=2)
            logger.info(f"Saved {len(job_ids)} job IDs to {args.output}")
            
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