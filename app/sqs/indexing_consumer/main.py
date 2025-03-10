import asyncio
import logging
import os
import signal

import ray

from app.core.config import settings
from app.core.container import container
from app.sqs.indexing_consumer.worker import process_messages, set_shutdown_flag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration from environment
AWS_REGION = settings.AWS_REGION
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '10'))


def handle_sigterm(signum, frame):
    """Handle SIGTERM signal for graceful shutdown."""
    logger.info("Received SIGTERM signal, initiating graceful shutdown")
    set_shutdown_flag()


async def main():
    """Main entry point for the SQS indexing consumer service using Ray."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Print startup banner
    logger.info("=" * 50)
    logger.info(
        f"Starting SQS consumer with Ray for queue: {settings.SQS_QUEUE_NAME}")
    logger.info(f"AWS Region: {AWS_REGION}")
    logger.info(f"Batch Size: {BATCH_SIZE}")
    logger.info(f"Available CPUs: {os.cpu_count()}")
    logger.info("=" * 50)

    # Initialize the container and all services
    try:
        logger.info("Initializing service container...")
        # Pass None since we don't have a FastAPI app here
        await container.initialize(None)
        logger.info("Service container initialized")
    except Exception as e:
        logger.error(f"Failed to initialize service container: {str(e)}")
        return 1

    # Initialize Ray
    try:
        if not ray.is_initialized():
            logger.info("Initializing Ray...")
            # Initialize Ray with sensible defaults for the container environment
            ray.init(
                ignore_reinit_error=True,
                include_dashboard=False,  # Completely disable the dashboard
                log_to_driver=True,
                _system_config={"object_spilling_config":
                                '{"type":"filesystem", "params":{"directory_path":"/tmp/ray_spill"}}'}
            )
            logger.info("Ray initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Ray: {str(e)}")
        return 1

    # Start message processing
    try:
        logger.info("Starting message processing with Ray")

        # Start message processing in a task
        process_task = asyncio.create_task(
            process_messages(
                sqs_service=container.sqs_service,
                region=AWS_REGION,
                batch_size=BATCH_SIZE
            )
        )

        # Wait for the process_messages task to complete (on shutdown)
        await process_task
    except Exception as e:
        logger.error(f"Error in message processing: {str(e)}")
        return 1
    finally:
        # Clean up all services
        logger.info("Cleaning up services...")
        await container.cleanup()
        logger.info("Service cleanup complete")

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
