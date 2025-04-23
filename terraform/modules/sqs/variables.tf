variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
}

variable "create_sqs_queue" {
  description = "Whether to create the SQS queue"
  type        = bool
  default     = false
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue"
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "The visibility timeout for the queue in seconds"
  type        = number
  default     = 900
}

variable "message_retention_seconds" {
  description = "The number of seconds Amazon SQS retains a message"
  type        = number
  default     = 345600  # 4 days
}

variable "max_message_size" {
  description = "The limit of how many bytes a message can contain before Amazon SQS rejects it"
  type        = number
  default     = 262144  # 256 KB
}

variable "delay_seconds" {
  description = "The time in seconds that the delivery of all messages in the queue will be delayed"
  type        = number
  default     = 0
}

variable "receive_wait_time_seconds" {
  description = "The time for which a ReceiveMessage call will wait for a message to arrive"
  type        = number
  default     = 0
}

variable "create_dlq" {
  description = "Whether to create a Dead Letter Queue"
  type        = bool
  default     = true
}

variable "max_receive_count" {
  description = "The number of times a message can be received before being sent to the DLQ"
  type        = number
  default     = 5
} 