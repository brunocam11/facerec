# SQS Outputs
output "sqs_queue_url" {
  description = "URL of the SQS queue"
  value       = "Using existing queue: ${var.sqs_queue_name}"
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = var.sqs_queue_arn
}

# IAM Outputs
output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = module.iam.ecs_task_execution_role_arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.iam.ecs_task_role_arn
}

output "instance_profile_name" {
  description = "Name of the ECS instance profile"
  value       = module.iam.ecs_instance_profile_name
}

# ASG Outputs
output "autoscaling_group_name" {
  description = "Name of the Auto Scaling Group"
  value       = module.asg.asg_name
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = module.asg.launch_template_id
}

# ECS Outputs
output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = module.ecs.ecs_cluster_id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.ecs_cluster_name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.ecs.ecs_cluster_arn
}

output "ecs_service_id" {
  description = "ID of the ECS service"
  value       = module.ecs.ecs_service_id
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.ecs.ecs_service_name
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = module.ecs.ecs_task_definition_arn
}

output "ecs_task_definition_family" {
  description = "Family of the ECS task definition"
  value       = module.ecs.ecs_task_definition_family
}

output "ecs_task_definition_revision" {
  description = "Revision of the ECS task definition"
  value       = module.ecs.ecs_task_definition_revision
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = module.ecs.cloudwatch_log_group_name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = module.ecs.cloudwatch_log_group_arn
}

output "sqs_queue_length_alarm_name" {
  description = "Name of the SQS queue length alarm"
  value       = module.ecs.sqs_queue_length_alarm_name
}

output "scale_down_alarm_name" {
  description = "Name of the scale down alarm"
  value       = module.ecs.scale_down_alarm_name
}

# Auto Scaling Policy Outputs
output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = module.asg.asg_name
}

output "asg_arn" {
  description = "ARN of the Auto Scaling Group"
  value       = module.asg.asg_arn
}

output "ecs_instance_profile_name" {
  description = "Name of the ECS instance profile"
  value       = module.iam.ecs_instance_profile_name
}

output "ecs_instance_profile_arn" {
  description = "ARN of the ECS instance profile"
  value       = module.iam.ecs_instance_profile_arn
}

output "ecs_task_execution_role_name" {
  description = "Name of the ECS task execution role"
  value       = module.iam.ecs_task_execution_role_name
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = module.iam.ecs_task_execution_role_arn
}

output "ecs_task_role_name" {
  description = "Name of the ECS task role"
  value       = module.iam.ecs_task_role_name
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.iam.ecs_task_role_arn
} 