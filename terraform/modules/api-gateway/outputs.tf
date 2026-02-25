# Outputs for API Gateway module

output "rest_api_endpoint" {
  description = "REST API Gateway endpoint URL"
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "rest_api_id" {
  description = "REST API Gateway ID"
  value       = aws_api_gateway_rest_api.main.id
}

# Secrets Manager outputs (replaces API key outputs)
output "api_key_secret_id" {
  description = "Secrets Manager secret ID for the unified API key"
  value       = aws_secretsmanager_secret.api_key.id
}

output "api_key_secret_arn" {
  description = "Secrets Manager secret ARN for the unified API key"
  value       = aws_secretsmanager_secret.api_key.arn
}

output "api_key_value" {
  description = "The generated API key value (sensitive)"
  value       = random_password.api_key.result
  sensitive   = true
}

output "websocket_api_endpoint" {
  description = "WebSocket API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.websocket.invoke_url
}

output "websocket_api_id" {
  description = "WebSocket API Gateway ID"
  value       = aws_apigatewayv2_api.websocket.id
}

output "lambda_people_count_arn" {
  description = "ARN of the People Count API Lambda function"
  value       = aws_lambda_function.people_count_api.arn
}

output "lambda_sensors_arn" {
  description = "ARN of the Sensors API Lambda function"
  value       = aws_lambda_function.sensors_api.arn
}

output "lambda_bus_position_arn" {
  description = "ARN of the Bus Position API Lambda function"
  value       = aws_lambda_function.bus_position_api.arn
}

output "lambda_websocket_arn" {
  description = "ARN of the WebSocket handler Lambda function"
  value       = aws_lambda_function.websocket_handler.arn
}

output "rest_authorizer_arn" {
  description = "ARN of the REST API Custom Authorizer Lambda function"
  value       = aws_lambda_function.rest_authorizer.arn
}

output "rest_authorizer_invoke_arn" {
  description = "Invoke ARN of the REST API Custom Authorizer Lambda function for API Gateway v2"
  value       = aws_lambda_function.rest_authorizer.invoke_arn
}

output "websocket_authorizer_arn" {
  description = "ARN of the WebSocket Custom Authorizer Lambda function"
  value       = aws_lambda_function.websocket_authorizer_v2.arn
}

