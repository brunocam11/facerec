variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution role"
  type        = string
  default     = "ecs-task-execution-role"
}

variable "ecs_task_role_name" {
  description = "Name of the ECS task role"
  type        = string
  default     = "ecs-task-role"
}

variable "ecs_instance_role_name" {
  description = "Name of the ECS instance role"
  type        = string
  default     = "ecs-instance-role"
} 