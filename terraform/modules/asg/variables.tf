variable "project" {
  description = "Project name"
  type        = string
  default     = "facerec"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "facerec"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "ID of the VPC where resources will be deployed"
  type        = string
  default     = ""
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the ECS instances"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
  default     = []
}

variable "cluster_name" {
  description = "ECS cluster name"
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile name"
  type        = string
}

variable "instance_type" {
  description = "Instance type for the launch template"
  type        = string
}

variable "fallback_instance_type" {
  description = "Fallback EC2 instance type for better spot availability"
  type        = string
  default     = "m5.2xlarge"
}

variable "ami_id" {
  description = "AMI ID for the launch template"
  type        = string
}

variable "asg_min_size" {
  description = "Minimum size of the Auto Scaling Group"
  type        = number
  default     = 0
}

variable "max_asg_size" {
  description = "Maximum size of the Auto Scaling Group"
  type        = number
  default     = 5
}

variable "asg_desired_capacity" {
  description = "Desired capacity of the Auto Scaling Group"
  type        = number
  default     = 0
}

variable "health_check_grace_period" {
  description = "Time (in seconds) after instance comes into service before checking health"
  type        = number
  default     = 300
}

variable "instance_warmup_period" {
  description = "The time (in seconds) for a new instance to warm up before it can be included in metrics for auto scaling"
  type        = number
  default     = 300
}

variable "ebs_volume_size" {
  description = "Size of the EBS volume in GB"
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

variable "subnet_ids" {
  description = "List of subnet IDs"
  type        = list(string)
  default     = []
} 