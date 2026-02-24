# Variables for Madrid Bus Real-Time Simulator Terraform configuration

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

variable "timestream_database_name" {
  description = "Name of the Timestream database"
  type        = string
  default     = "bus_simulator"
}

variable "participant_count" {
  description = "Number of API keys to generate for hackathon participants"
  type        = number
  default     = 12
}

variable "create_vpc" {
  description = "Whether to create a new VPC or use existing"
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "CIDR block for VPC if creating new"
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "Madrid-Bus-Simulator"
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD for cost monitoring"
  type        = number
  default     = 200
}

variable "budget_alert_emails" {
  description = "Email addresses to receive budget alert notifications"
  type        = list(string)
  default     = []
}

# MCP Server configuration
variable "mcp_cpu" {
  description = "CPU units for MCP server task (256 = 0.25 vCPU, 512 = 0.5 vCPU, 1024 = 1 vCPU)"
  type        = string
  default     = "512"
}

variable "mcp_memory" {
  description = "Memory for MCP server task in MB"
  type        = string
  default     = "1024"
}

variable "mcp_log_level" {
  description = "Log level for MCP server (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
}

variable "mcp_cors_allowed_origins" {
  description = "List of allowed origins for CORS on MCP API Gateway"
  type        = list(string)
  default     = ["*"]
}

variable "enable_vpc_endpoints" {
  description = "Whether to create VPC endpoints for private communication with AWS services (Secrets Manager, Timestream, CloudWatch Logs)"
  type        = bool
  default     = true
}

