# Outputs for Madrid Bus Real-Time Simulator Terraform configuration

# Timestream outputs
output "timestream_database_name" {
  description = "Name of the Timestream database"
  value       = module.timestream.database_name
}

output "timestream_table_names" {
  description = "Names of the Timestream tables"
  value       = module.timestream.table_names
}

# API Gateway outputs
output "api_gateway_rest_endpoint" {
  description = "REST API Gateway endpoint URL"
  value       = module.api_gateway.rest_api_endpoint
}

output "api_gateway_rest_api_id" {
  description = "REST API Gateway ID"
  value       = module.api_gateway.rest_api_id
}

output "api_gateway_websocket_endpoint" {
  description = "WebSocket API Gateway endpoint URL"
  value       = module.api_gateway.websocket_api_endpoint
}

# Secrets Manager outputs (replaces API key outputs)
output "api_key_secret_id" {
  description = "Secrets Manager secret ID for the unified API key"
  value       = module.api_gateway.api_key_secret_id
}

output "api_key_secret_arn" {
  description = "Secrets Manager secret ARN for the unified API key"
  value       = module.api_gateway.api_key_secret_arn
}

output "api_key_value" {
  description = "The generated API key value (use scripts/export_api_key.py to retrieve)"
  value       = module.api_gateway.api_key_value
  sensitive   = true
}
# Fargate outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.fargate.cluster_name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = module.fargate.ecr_repository_url
}

# Supporting resources outputs
output "config_bucket_name" {
  description = "Name of the S3 bucket for configuration"
  value       = module.supporting.config_bucket_name
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for WebSocket connections"
  value       = module.supporting.dynamodb_table_name
}

# EventBridge outputs
output "eventbridge_bus_name" {
  description = "Name of the EventBridge event bus"
  value       = module.eventbridge.event_bus_name
}

# Amazon Location outputs
output "location_route_calculator_name" {
  description = "Name of the Amazon Location route calculator"
  value       = module.location.route_calculator_name
}

output "location_map_name" {
  description = "Name of the Amazon Location map"
  value       = module.location.map_name
}

# Cost Management outputs
output "budget_name" {
  description = "Name of the AWS Budget for cost monitoring"
  value       = module.cost_management.budget_name
}

output "budget_alert_sns_topic" {
  description = "ARN of the SNS topic for budget alerts"
  value       = module.cost_management.sns_topic_arn
}

# MCP Server outputs
output "mcp_server_service_name" {
  description = "Name of the MCP server ECS service"
  value       = module.mcp_server.service_name
}

output "mcp_server_task_definition_arn" {
  description = "ARN of the MCP server task definition"
  value       = module.mcp_server.task_definition_arn
}

output "mcp_server_log_group" {
  description = "CloudWatch log group for MCP server"
  value       = module.supporting.mcp_log_group_name
}

# MCP API Gateway outputs
output "mcp_api_endpoint" {
  description = "MCP Server HTTP API Gateway endpoint URL"
  value       = module.mcp_server.api_endpoint
}

output "mcp_api_id" {
  description = "MCP Server HTTP API Gateway ID"
  value       = module.mcp_server.api_id
}

# VPC Endpoints outputs
output "vpc_endpoints_enabled" {
  description = "Whether VPC endpoints are enabled for private AWS service communication"
  value       = var.enable_vpc_endpoints
}

output "secrets_manager_endpoint_id" {
  description = "ID of the Secrets Manager VPC endpoint (if enabled)"
  value       = module.supporting.secrets_manager_endpoint_id
}

output "logs_endpoint_id" {
  description = "ID of the CloudWatch Logs VPC endpoint (if enabled)"
  value       = module.supporting.logs_endpoint_id
}

output "timestream_ingest_endpoint_id" {
  description = "ID of the Timestream Ingest VPC endpoint (if enabled)"
  value       = module.supporting.timestream_ingest_endpoint_id
}

output "timestream_query_endpoint_id" {
  description = "ID of the Timestream Query VPC endpoint (if enabled)"
  value       = module.supporting.timestream_query_endpoint_id
}

