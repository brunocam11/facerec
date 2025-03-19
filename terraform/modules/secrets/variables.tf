variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
}

variable "create_secrets" {
  description = "Whether to create new secrets in AWS Secrets Manager"
  type        = bool
  default     = false
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "pinecone_api_key_arn" {
  description = "ARN of existing Secret Manager secret containing Pinecone API key"
  type        = string
  default     = ""
} 