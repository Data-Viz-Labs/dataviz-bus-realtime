# Outputs for API Gateway module

output "http_api_endpoint" {
  description = "HTTP API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.http.invoke_url
}

output "http_api_id" {
  description = "HTTP API Gateway ID"
  value       = aws_apigatewayv2_api.http.id
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
