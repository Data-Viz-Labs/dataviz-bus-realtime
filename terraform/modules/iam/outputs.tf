# Outputs for IAM module

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.name
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "ecs_task_role_name" {
  description = "Name of the ECS task role"
  value       = aws_iam_role.ecs_task.name
}

output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  value       = aws_iam_role.ecs_execution.arn
}

output "ecs_execution_role_name" {
  description = "Name of the ECS execution role"
  value       = aws_iam_role.ecs_execution.name
}

output "apigateway_cloudwatch_role_arn" {
  description = "ARN of the API Gateway CloudWatch Logs role"
  value       = aws_iam_role.apigateway_cloudwatch.arn
}

output "mcp_task_role_arn" {
  description = "ARN of the MCP server task role"
  value       = aws_iam_role.mcp_task.arn
}

output "mcp_task_role_name" {
  description = "Name of the MCP server task role"
  value       = aws_iam_role.mcp_task.name
}
