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

variable "aws_profile" {
  description = "AWS profile to use for authentication"
  type        = string
  default     = "default"
}

# ECR Settings
variable "ecr_repository_url" {
  description = "URL of the ECR repository"
  type        = string
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository containing the container image"
  type        = string
  default     = "facerec-worker"
}

# ECS Settings
variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
  default     = "facerec-worker-cluster"
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

# Task Settings
variable "task_cpu" {
  description = "CPU units for the task"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Memory for the task"
  type        = number
  default     = 2048
}

# S3 Settings
variable "s3_bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
}

variable "s3_bucket_region" {
  description = "Region of the S3 bucket"
  type        = string
}

# Pinecone Settings
variable "pinecone_index_name" {
  description = "Name of the Pinecone index"
  type        = string
}

variable "pinecone_api_key" {
  description = "Pinecone API key for face recognition service"
  type        = string
  sensitive   = true
}

# Face Recognition Settings
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

# SQS Settings
variable "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  type        = string
}

variable "create_sqs_queue" {
  description = "Whether to create a new SQS queue or use an existing one"
  type        = bool
  default     = false
}

variable "sqs_visibility_timeout" {
  description = "Visibility timeout for SQS messages"
  type        = number
  default     = 600
}

variable "sqs_message_retention_seconds" {
  description = "Message retention period for SQS in seconds"
  type        = number
  default     = 345600  # 4 days
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue"
  type        = string
  default     = "facerec-queue"
}

# Auto Scaling Settings
variable "ecs_service_min_capacity" {
  description = "Minimum capacity for the ECS service"
  type        = number
  default     = 0
}

variable "ecs_service_max_capacity" {
  description = "Maximum capacity for the ECS service"
  type        = number
  default     = 10
}

variable "target_value" {
  description = "Target value for auto scaling"
  type        = number
  default     = 1
}

variable "scale_in_cooldown" {
  description = "Cooldown period for scale in"
  type        = number
  default     = 300
}

variable "scale_out_cooldown" {
  description = "Cooldown period for scale out"
  type        = number
  default     = 30
}

# VPC Settings
variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
  default     = ""
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
  default     = []
}

# EC2 Settings
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "fallback_instance_type" {
  description = "Fallback EC2 instance type if primary is unavailable"
  type        = string
  default     = "m5.2xlarge"
}

variable "ami_id" {
  description = "AMI ID for EC2 instances"
  type        = string
}

# ASG Settings
variable "asg_min_size" {
  description = "Minimum size of the Auto Scaling Group"
  type        = number
  default     = 0
}

variable "max_asg_size" {
  description = "Maximum size of the Auto Scaling Group"
  type        = number
  default     = 10
}

variable "asg_desired_capacity" {
  description = "Desired capacity of the Auto Scaling Group"
  type        = number
  default     = 0
}

# Instance Settings
variable "health_check_grace_period" {
  description = "Grace period for health checks"
  type        = number
  default     = 300
}

variable "instance_warmup_period" {
  description = "Warmup period for instances"
  type        = number
  default     = 300
}

# EBS Settings
variable "ebs_volume_size" {
  description = "Size of the EBS volume"
  type        = number
  default     = 30
}

variable "ebs_volume_type" {
  description = "Type of the EBS volume"
  type        = string
  default     = "gp3"
}

variable "ebs_delete_on_termination" {
  description = "Whether to delete the EBS volume on instance termination"
  type        = bool
  default     = true
}

# Secrets Management
variable "create_secrets" {
  description = "Whether to create new secrets in AWS Secrets Manager"
  type        = bool
  default     = false
} 