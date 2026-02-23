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
/*
output "api_keys" {
  description = "List of API key IDs for hackathon participants"
  value       = module.api_gateway.api_keys
  sensitive   = true
}

output "api_key_values" {
  description = "List of API key values for hackathon participants (use for distribution)"
  value       = module.api_gateway.api_key_values
  sensitive   = true
}

output "usage_plan_id" {
  description = "Usage plan ID for hackathon participants"
  value       = module.api_gateway.usage_plan_id
}
*/
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
