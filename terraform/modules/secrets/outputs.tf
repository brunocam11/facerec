output "pinecone_api_key_arn" {
  description = "ARN of the Pinecone API key secret"
  value       = var.create_secrets ? aws_secretsmanager_secret.pinecone_api_key[0].arn : var.pinecone_api_key_arn
} 