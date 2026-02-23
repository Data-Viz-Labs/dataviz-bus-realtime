#
# CloudWatch Log Group for API Gateway access logs
# #############################################################################

resource "aws_cloudwatch_log_group" "api_gateway_access_logs" {
  name              = "/aws/apigateway/${aws_api_gateway_rest_api.main.name}"
  retention_in_days = 7

  tags = var.tags
}

#
# CloudWatch Log Groups for Lambda functions
# #############################################################################

resource "aws_cloudwatch_log_group" "people_count_api" {
  name              = "/aws/lambda/bus-simulator-people-count"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "sensors_api" {
  name              = "/aws/lambda/bus-simulator-sensors"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "bus_position_api" {
  name              = "/aws/lambda/bus-simulator-bus-position"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "websocket_handler" {
  name              = "/aws/lambda/bus-simulator-websocket"
  retention_in_days = 30

  tags = var.tags
}


