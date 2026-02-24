# Variables for MCP Server module

variable "ecs_cluster_id" {
  description = "ID of the ECS cluster where MCP server will be deployed"
  type        = string
}

variable "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role for pulling images and writing logs"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository containing the MCP server image"
  type        = string
}

variable "timestream_database_name" {
  description = "Name of the Timestream database"
  type        = string
}

variable "api_key_secret_id" {
  description = "Secrets Manager secret ID for the API key"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS service deployment"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for the MCP server ECS service"
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch log group name for MCP server logs"
  type        = string
}

variable "cpu" {
  description = "CPU units for the MCP server task (256 = 0.25 vCPU, 512 = 0.5 vCPU, 1024 = 1 vCPU)"
  type        = string
  default     = "512"
}

variable "memory" {
  description = "Memory for the MCP server task in MB"
  type        = string
  default     = "1024"
}

variable "container_port" {
  description = "Port on which the MCP server listens"
  type        = number
  default     = 8080
}

variable "desired_count" {
  description = "Desired number of MCP server tasks to run"
  type        = number
  default     = 1
}

variable "log_level" {
  description = "Log level for the MCP server (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
}

variable "enable_execute_command" {
  description = "Enable ECS Exec for debugging"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}


# API Gateway HTTP API variables
variable "vpc_id" {
  description = "VPC ID for Service Discovery namespace"
  type        = string
}

variable "vpc_link_security_group_id" {
  description = "Security group ID for VPC Link"
  type        = string
}

variable "rest_authorizer_invoke_arn" {
  description = "Invoke ARN of the REST API Custom Authorizer Lambda function"
  type        = string
}

variable "rest_authorizer_function_name" {
  description = "Function name of the REST API Custom Authorizer Lambda"
  type        = string
}

variable "cors_allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = ["*"]
}

variable "throttling_burst_limit" {
  description = "API Gateway throttling burst limit"
  type        = number
  default     = 100
}

variable "throttling_rate_limit" {
  description = "API Gateway throttling rate limit (requests per second)"
  type        = number
  default     = 50
}

variable "api_log_group_arn" {
  description = "ARN of CloudWatch log group for API Gateway access logs (optional, will be created if not provided)"
  type        = string
  default     = ""
}
