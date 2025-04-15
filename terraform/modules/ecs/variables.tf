variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository"
  type        = string
}

variable "ecs_container_name" {
  description = "Name of the ECS container"
  type        = string
}

variable "ecs_task_family" {
  description = "Family name for the ECS task definition"
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "task_cpu" {
  description = "CPU units for the task (default: 100% of instance CPU)"
  type        = number
  default     = 8192  # 8 vCPUs for c5.2xlarge
}

variable "task_memory" {
  description = "Memory for the task (default: 100% of instance memory)"
  type        = number
  default     = 16384  # 16GB for c5.2xlarge
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "s3_bucket_region" {
  description = "Region of the S3 bucket"
  type        = string
}

variable "pinecone_index_name" {
  description = "Name of the Pinecone index"
  type        = string
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "max_faces_per_image" {
  description = "Maximum number of faces to detect per image"
  type        = string
  default     = "10"
}

variable "min_face_confidence" {
  description = "Minimum confidence threshold for face detection"
  type        = string
  default     = "0.5"
}

variable "similarity_threshold" {
  description = "Threshold for face similarity matching"
  type        = string
  default     = "0.8"
}

variable "container_memory_threshold" {
  description = "Memory threshold for container"
  type        = string
  default     = "0.8"
}

variable "ray_memory_per_process" {
  description = "Memory per Ray process"
  type        = string
  default     = "0.5"
}

variable "sqs_batch_size" {
  description = "Batch size for SQS messages"
  type        = string
  default     = "10"
}

variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue to monitor for scaling"
  type        = string
}

variable "autoscaling_group_name" {
  description = "Name of the Auto Scaling Group"
  type        = string
} 