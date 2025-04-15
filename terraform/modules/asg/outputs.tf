output "asg_arn" {
  description = "ARN of the Auto Scaling Group"
  value       = aws_autoscaling_group.facerec_asg.arn
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.facerec_asg.name
}

output "asg_capacity_provider_name" {
  description = "Name of the ASG capacity provider"
  value       = "${var.project}-capacity-provider-${var.environment}"
}

output "asg_capacity_provider_arn" {
  description = "ARN of the ASG capacity provider"
  value       = ""  # This will be created by the ECS module with the ASG ARN
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = aws_launch_template.ecs_launch_template.id
}

output "launch_template_arn" {
  description = "ARN of the Launch Template"
  value       = aws_launch_template.ecs_launch_template.arn
}

output "launch_template_latest_version" {
  description = "Latest version of the Launch Template"
  value       = aws_launch_template.ecs_launch_template.latest_version
} 