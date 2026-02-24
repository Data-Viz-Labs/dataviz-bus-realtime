# Variables for IAM module

variable "timestream_database_arn" {
  description = "ARN of the Timestream database"
  type        = string
}

variable "timestream_table_arns" {
  description = "List of Timestream table ARNs"
  type        = list(string)
}

variable "eventbridge_bus_arn" {
  description = "ARN of the EventBridge event bus"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table for WebSocket connections"
  type        = string
}

variable "config_bucket_arn" {
  description = "ARN of the S3 bucket for configuration"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "api_key_secret_arn" {
  description = "ARN of the Secrets Manager secret for API key"
  type        = string
}
