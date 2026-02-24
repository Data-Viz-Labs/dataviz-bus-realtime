# Secrets Manager for unified API key management
# Replaces API Gateway API keys with centralized secret storage

# Generate a single API key for all participants
resource "random_password" "api_key" {
  length  = 32
  special = false
}

# Store API key in Secrets Manager
resource "aws_secretsmanager_secret" "api_key" {
  name        = "bus-simulator/api-key"
  description = "Unified API key for Madrid Bus Simulator - used by Custom Authorizers"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id = aws_secretsmanager_secret.api_key.id
  secret_string = jsonencode({
    api_key = random_password.api_key.result
  })
}
