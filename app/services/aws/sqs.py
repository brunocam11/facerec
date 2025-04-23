"""
SQS service for message queue operations.
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import boto3

from app.core.config import settings

logger = logging.getLogger(__name__)


class SQSService:
    """Service for interacting with AWS SQS queues for face recognition tasks."""

    def __init__(
        self,
        region_name: Optional[str] = None,
        queue_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None
    ):
        """
        Initialize the SQS service with AWS credentials.

        Args:
            region_name: AWS region name (defaults to settings)
            queue_name: SQS queue name (defaults to settings)
            access_key_id: AWS access key ID (defaults to settings)
            secret_access_key: AWS secret access key (defaults to settings)
        """
        self.region_name = region_name or settings.AWS_REGION
        self.queue_name = queue_name or settings.SQS_QUEUE_NAME
        self.access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY
        self.sqs = None
        self.queue = None
        self.queue_url = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the SQS client and get the queue."""
        if self.initialized:
            return

        try:
            logger.info(
                f"Initializing SQS service for queue: {self.queue_name}")

            self.sqs = boto3.resource(
                'sqs',
                region_name=self.region_name,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key
            )

            # Get the queue by name
            self.queue = self.sqs.get_queue_by_name(QueueName=self.queue_name)
            self.queue_url = self.queue.url

            logger.info(
                f"Successfully initialized SQS service for queue: {self.queue_name}")
            self.initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize SQS service: {str(e)}")
            raise

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up SQS service resources")
        # The boto3 clients don't need explicit cleanup
        self.initialized = False

    async def send_message(self, message_body: Dict[str, Any]) -> str:
        """
        Send a message to the SQS queue.

        Args:
            message_body: Dictionary containing message data

        Returns:
            The message ID (job_id)
        """
        if not self.initialized:
            await self.initialize()

        # Generate a unique job ID
        job_id = str(uuid.uuid4())

        # Add job_id to the message body
        message_body['job_id'] = job_id

        try:
            # Send message to SQS
            response = self.queue.send_message(
                MessageBody=json.dumps(message_body)
            )
            logger.info(f"Successfully enqueued job {job_id} to SQS")
            return job_id
        except Exception as e:
            logger.error(f"Failed to send message to SQS: {str(e)}")
            raise

    async def receive_messages(self, max_messages: int = 10, wait_time: int = 20) -> List[Dict]:
        """
        Receive messages from the SQS queue.

        Args:
            max_messages: Maximum number of messages to receive (1-10)
            wait_time: Long polling wait time in seconds

        Returns:
            List of received messages with their receipt handles
        """
        if not self.initialized:
            await self.initialize()

        try:
            messages = list(self.queue.receive_messages(
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            ))

            result = []
            for msg in messages:
                try:
                    body = json.loads(msg.body)
                    result.append({
                        'receipt_handle': msg.receipt_handle,
                        'body': body,
                        'message_id': msg.message_id
                    })
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode message body: {msg.body}")

            return result
        except Exception as e:
            logger.error(f"Failed to receive messages from SQS: {str(e)}")
            raise

    async def delete_message(self, receipt_handle: str) -> bool:
        """
        Delete a message from the queue after processing.

        Args:
            receipt_handle: The receipt handle of the message to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            await self.initialize()

        try:
            self.queue.delete_messages(
                Entries=[{
                    'Id': str(uuid.uuid4()),
                    'ReceiptHandle': receipt_handle
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete message from SQS: {str(e)}")
            return False
