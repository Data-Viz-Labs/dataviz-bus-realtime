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
