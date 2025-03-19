output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.facerec_worker.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.facerec_worker.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.facerec_worker.arn
}

output "ecs_service_id" {
  description = "ID of the ECS service"
  value       = aws_ecs_service.facerec_worker.id
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.facerec_worker.name
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition"
  value       = aws_ecs_task_definition.facerec_worker.arn
}

output "ecs_task_definition_family" {
  description = "Family of the ECS task definition"
  value       = aws_ecs_task_definition.facerec_worker.family
}

output "ecs_task_definition_revision" {
  description = "Revision of the ECS task definition"
  value       = aws_ecs_task_definition.facerec_worker.revision
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.facerec_worker.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.facerec_worker.arn
}

output "sqs_queue_length_alarm_name" {
  description = "Name of the SQS queue length alarm"
  value       = aws_cloudwatch_metric_alarm.sqs_queue_length.alarm_name
}

output "scale_down_alarm_name" {
  description = "Name of the scale down alarm"
  value       = aws_cloudwatch_metric_alarm.scale_down.alarm_name
} 