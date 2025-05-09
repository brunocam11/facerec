import asyncio
import logging
import os

import psutil
import ray

from app.consumers.indexing_consumer.worker import process_messages
from app.core.config import settings
from app.core.container import container

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_ray():
    """Initialize Ray with calculated resources.

    Returns:
        int: Number of CPUs allocated to Ray
    """
    # Get available system resources
    total_memory_gb = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    total_cpus = os.cpu_count()

    # Reserve 1GB for main process and Ray overhead
    reserved_memory_gb = 1
    usable_memory_gb = total_memory_gb - reserved_memory_gb

    # First determine how many CPUs we can use (using 3GB per CPU rule)
    base_cpus = max(1, int(usable_memory_gb / 3))

    # Cap at physical CPU count minus 1 (for system operations)
    usable_cpus = min(base_cpus, total_cpus - 1)
    usable_cpus = max(1, usable_cpus)  # Ensure at least 1 CPU

    # Calculate actual memory per CPU to utilize all available RAM
    # Convert to MB and make it an integer (Ray requires whole numbers)
    memory_per_cpu_mb = int(usable_memory_gb * 1024 / usable_cpus)

    logger.info(
        f"System has {total_cpus} CPUs and {total_memory_gb:.1f}GB RAM")
    logger.info(
        f"Allocating {usable_cpus} CPUs for Ray with {memory_per_cpu_mb}MB per CPU")

    ray.init(
        ignore_reinit_error=True,
        num_cpus=usable_cpus,
        resources={'memory_per_cpu_mb': memory_per_cpu_mb}
    )

    # Allow using 95% of memory
    os.environ['RAY_memory_usage_threshold'] = '0.95'

    return usable_cpus


async def main():
    """Main entry point for the SQS indexing consumer service using Ray."""
    # Print startup banner
    logger.info("=" * 50)
    logger.info(
        f"Starting SQS consumer with Ray for queue: {settings.SQS_QUEUE_NAME}")
    logger.info(f"AWS Region: {settings.AWS_REGION}")
    logger.info(f"Batch Size: {settings.SQS_BATCH_SIZE}")
    logger.info(f"Available CPUs: {os.cpu_count()}")
    logger.info("=" * 50)

    # Initialize the container and all services
    try:
        logger.info("Initializing service container...")
        await container.initialize()
        logger.info("Service container initialized")
    except Exception as e:
        logger.error(f"Failed to initialize service container: {str(e)}")
        return 1

    # Initialize Ray
    try:
        # Always shutdown Ray if it's already running to ensure a clean state
        if ray.is_initialized():
            logger.info("Ray already initialized, shutting down first...")
            ray.shutdown()

        logger.info("Initializing Ray...")
        # Initialize Ray with calculated resources
        usable_cpus = initialize_ray()
        logger.info(f"Ray initialized with {usable_cpus} CPUs")
    except Exception as e:
        logger.error(f"Failed to initialize Ray: {str(e)}")
        return 1

    # Start message processing
    try:
        logger.info("Starting message processing with Ray")
        await process_messages(
            sqs_service=container.sqs_service,
            region=settings.AWS_REGION
        )
    except Exception as e:
        logger.error(f"Error in message processing: {str(e)}")
        return 1
    finally:
        # Clean up all services
        logger.info("Cleaning up services...")
        await container.cleanup()
        logger.info("Service cleanup complete")

        # Shutdown Ray
        if ray.is_initialized():
            logger.info("Shutting down Ray...")
            ray.shutdown()
            logger.info("Ray shutdown complete")

    logger.info("Service shutdown complete")
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
        exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        exit(1)
