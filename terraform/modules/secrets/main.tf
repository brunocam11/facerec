# Pinecone API Key Secret
resource "aws_secretsmanager_secret" "pinecone_api_key" {
  count = var.create_secrets ? 1 : 0
  
  name        = "${var.project_name}-pinecone-api-key-${var.environment}"
  description = "Pinecone API key for face recognition service"
  
  tags = {
    Name        = "${var.project_name}-pinecone-api-key-${var.environment}"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_secretsmanager_secret_version" "pinecone_api_key" {
  count = var.create_secrets ? 1 : 0
  
  secret_id     = aws_secretsmanager_secret.pinecone_api_key[0].id
  secret_string = var.pinecone_api_key
} 