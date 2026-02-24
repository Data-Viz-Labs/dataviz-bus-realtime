# Outputs for Supporting resources module

output "vpc_id" {
  description = "ID of the VPC"
  value       = var.create_vpc ? aws_vpc.main[0].id : null
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = var.create_vpc ? aws_subnet.private[*].id : []
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = var.create_vpc ? aws_subnet.public[*].id : []
}

output "fargate_security_group_id" {
  description = "ID of the Fargate security group"
  value       = var.create_vpc ? aws_security_group.fargate[0].id : null
}

output "config_bucket_name" {
  description = "Name of the S3 configuration bucket"
  value       = aws_s3_bucket.config.id
}

output "config_bucket_arn" {
  description = "ARN of the S3 configuration bucket"
  value       = aws_s3_bucket.config.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB WebSocket connections table"
  value       = aws_dynamodb_table.websocket_connections.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB WebSocket connections table"
  value       = aws_dynamodb_table.websocket_connections.arn
}

output "mcp_security_group_id" {
  description = "ID of the MCP server security group"
  value       = var.create_vpc ? aws_security_group.mcp_server[0].id : null
}

output "vpc_link_security_group_id" {
  description = "ID of the VPC Link security group"
  value       = var.create_vpc ? aws_security_group.vpc_link[0].id : null
}

output "mcp_log_group_name" {
  description = "Name of the MCP server CloudWatch log group"
  value       = aws_cloudwatch_log_group.mcp_server.name
}

output "mcp_log_group_arn" {
  description = "ARN of the MCP server CloudWatch log group"
  value       = aws_cloudwatch_log_group.mcp_server.arn
}

output "mcp_api_log_group_arn" {
  description = "ARN of the MCP API Gateway CloudWatch log group"
  value       = "${aws_cloudwatch_log_group.mcp_server.arn}-api"
}

output "vpc_endpoints_security_group_id" {
  description = "ID of the VPC endpoints security group"
  value       = var.create_vpc && var.enable_vpc_endpoints ? aws_security_group.vpc_endpoints[0].id : null
}

output "secrets_manager_endpoint_id" {
  description = "ID of the Secrets Manager VPC endpoint"
  value       = var.create_vpc && var.enable_vpc_endpoints ? aws_vpc_endpoint.secrets_manager[0].id : null
}

output "logs_endpoint_id" {
  description = "ID of the CloudWatch Logs VPC endpoint"
  value       = var.create_vpc && var.enable_vpc_endpoints ? aws_vpc_endpoint.logs[0].id : null
}

output "timestream_ingest_endpoint_id" {
  description = "ID of the Timestream Ingest VPC endpoint"
  value       = var.create_vpc && var.enable_vpc_endpoints ? aws_vpc_endpoint.timestream_ingest[0].id : null
}

output "timestream_query_endpoint_id" {
  description = "ID of the Timestream Query VPC endpoint"
  value       = var.create_vpc && var.enable_vpc_endpoints ? aws_vpc_endpoint.timestream_query[0].id : null
}

