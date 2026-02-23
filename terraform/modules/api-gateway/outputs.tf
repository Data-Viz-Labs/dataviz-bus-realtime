# Outputs for API Gateway module

output "rest_api_endpoint" {
  description = "REST API Gateway endpoint URL"
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "rest_api_id" {
  description = "REST API Gateway ID"
  value       = aws_api_gateway_rest_api.main.id
}
/*
output "api_keys" {
  description = "List of API key IDs for hackathon participants"
  value       = aws_api_gateway_api_key.participant_keys[*].id
  sensitive   = true
}

output "api_key_values" {
  description = "List of API key values for hackathon participants"
  value       = aws_api_gateway_api_key.participant_keys[*].value
  sensitive   = true
}

output "usage_plan_id" {
  description = "Usage plan ID for hackathon participants"
  value       = aws_api_gateway_usage_plan.hackathon.id
}
*/
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
