# Outputs for MCP Server module

output "task_definition_arn" {
  description = "ARN of the MCP server ECS task definition"
  value       = aws_ecs_task_definition.mcp_server.arn
}

output "service_name" {
  description = "Name of the MCP server ECS service"
  value       = aws_ecs_service.mcp_server.name
}

output "service_id" {
  description = "ID of the MCP server ECS service"
  value       = aws_ecs_service.mcp_server.id
}


# API Gateway outputs
output "api_endpoint" {
  description = "MCP Server HTTP API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.prod.invoke_url
}

output "api_id" {
  description = "MCP Server HTTP API Gateway ID"
  value       = aws_apigatewayv2_api.mcp.id
}

output "vpc_link_id" {
  description = "VPC Link ID for API Gateway integration"
  value       = aws_apigatewayv2_vpc_link.mcp.id
}

output "service_discovery_namespace_id" {
  description = "Service Discovery namespace ID"
  value       = aws_service_discovery_private_dns_namespace.mcp.id
}

output "service_discovery_service_arn" {
  description = "Service Discovery service ARN"
  value       = aws_service_discovery_service.mcp_server.arn
}

# IAM role outputs
output "task_role_arn" {
  description = "ARN of the IAM role for MCP server ECS task"
  value       = aws_iam_role.mcp_task_role.arn
}

output "task_role_name" {
  description = "Name of the IAM role for MCP server ECS task"
  value       = aws_iam_role.mcp_task_role.name
}

# Network Load Balancer outputs
output "nlb_arn" {
  description = "ARN of the Network Load Balancer"
  value       = aws_lb.mcp.arn
}

output "nlb_dns_name" {
  description = "DNS name of the Network Load Balancer"
  value       = aws_lb.mcp.dns_name
}

output "target_group_arn" {
  description = "ARN of the NLB target group"
  value       = aws_lb_target_group.mcp.arn
}
