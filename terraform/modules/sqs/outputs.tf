output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = var.create_sqs_queue ? aws_sqs_queue.facerec_indexing[0].arn : ""
}

output "sqs_queue_url" {
  description = "URL of the SQS queue"
  value       = var.create_sqs_queue ? aws_sqs_queue.facerec_indexing[0].url : ""
}

output "dlq_queue_arn" {
  description = "ARN of the Dead Letter Queue"
  value       = var.create_sqs_queue && var.create_dlq ? aws_sqs_queue.facerec_indexing_dlq[0].arn : ""
}

output "dlq_queue_url" {
  description = "URL of the Dead Letter Queue"
  value       = var.create_sqs_queue && var.create_dlq ? aws_sqs_queue.facerec_indexing_dlq[0].url : ""
} 