# Create Dead Letter Queue if enabled
resource "aws_sqs_queue" "facerec_indexing_dlq" {
  count = var.create_sqs_queue && var.create_dlq ? 1 : 0
  
  name                      = "${var.sqs_queue_name}-dlq"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds = var.message_retention_seconds
  max_message_size          = var.max_message_size
  delay_seconds             = var.delay_seconds
  receive_wait_time_seconds = var.receive_wait_time_seconds
  
  tags = {
    Name        = "${var.sqs_queue_name}-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Create main SQS queue if enabled
resource "aws_sqs_queue" "facerec_indexing" {
  count = var.create_sqs_queue ? 1 : 0
  
  name                      = var.sqs_queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds = var.message_retention_seconds
  max_message_size          = var.max_message_size
  delay_seconds             = var.delay_seconds
  receive_wait_time_seconds = var.receive_wait_time_seconds
  
  # Set up redrive policy to DLQ if it exists
  redrive_policy = var.create_dlq ? jsonencode({
    deadLetterTargetArn = aws_sqs_queue.facerec_indexing_dlq[0].arn
    maxReceiveCount     = var.max_receive_count
  }) : null
  
  tags = {
    Name        = var.sqs_queue_name
    Environment = var.environment
    Project     = var.project_name
  }
}

# Create SQS Queue Policy to allow ECS tasks to access the queue
resource "aws_sqs_queue_policy" "facerec_indexing" {
  count     = var.create_sqs_queue ? 1 : 0
  queue_url = aws_sqs_queue.facerec_indexing[0].url
  
  policy = jsonencode({
    Version = "2012-10-17",
    Id      = "${var.sqs_queue_name}-policy",
    Statement = [
      {
        Sid       = "AllowECSTasksToAccessQueue",
        Effect    = "Allow",
        Principal = {
          AWS = "*" # Will be restricted by condition
        },
        Action    = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ],
        Resource  = aws_sqs_queue.facerec_indexing[0].arn,
        Condition = {
          ArnLike = {
            "aws:SourceArn": "arn:aws:ecs:*:*:*"
          }
        }
      }
    ]
  })
} 