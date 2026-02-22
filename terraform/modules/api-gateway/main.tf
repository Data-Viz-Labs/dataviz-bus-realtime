# API Gateway module for Madrid Bus Real-Time Simulator
# Creates HTTP API and WebSocket API with Lambda integrations

# Lambda functions
resource "aws_lambda_function" "people_count_api" {
  filename         = "${path.root}/../build/people_count_api.zip"
  function_name    = "bus-simulator-people-count"
  role            = var.lambda_execution_role_arn
  handler         = "people_count_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/people_count_api.zip")
  runtime         = "python3.11"
  timeout         = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.people_count
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "sensors_api" {
  filename         = "${path.root}/../build/sensors_api.zip"
  function_name    = "bus-simulator-sensors"
  role            = var.lambda_execution_role_arn
  handler         = "sensors_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/sensors_api.zip")
  runtime         = "python3.11"
  timeout         = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.sensor_data
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "bus_position_api" {
  filename         = "${path.root}/../build/bus_position_api.zip"
  function_name    = "bus-simulator-bus-position"
  role            = var.lambda_execution_role_arn
  handler         = "bus_position_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/bus_position_api.zip")
  runtime         = "python3.11"
  timeout         = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.bus_position
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "websocket_handler" {
  filename         = "${path.root}/../build/websocket_handler.zip"
  function_name    = "bus-simulator-websocket"
  role            = var.lambda_execution_role_arn
  handler         = "websocket_handler.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/websocket_handler.zip")
  runtime         = "python3.11"
  timeout         = 30

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
    }
  }

  tags = var.tags
}

# HTTP API Gateway
resource "aws_apigatewayv2_api" "http" {
  name          = "bus-simulator-http-api"
  protocol_type = "HTTP"
  description   = "HTTP API for Madrid Bus Real-Time Simulator"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }

  tags = var.tags
}

resource "aws_apigatewayv2_stage" "http" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  tags = var.tags
}

# HTTP API integrations
resource "aws_apigatewayv2_integration" "people_count" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.people_count_api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "sensors" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.sensors_api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "bus_position" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.bus_position_api.invoke_arn
  payload_format_version = "2.0"
}

# HTTP API routes
resource "aws_apigatewayv2_route" "people_count" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /people-count/{stop_id}"
  target    = "integrations/${aws_apigatewayv2_integration.people_count.id}"
}

resource "aws_apigatewayv2_route" "sensors" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /sensors/{entity_type}/{entity_id}"
  target    = "integrations/${aws_apigatewayv2_integration.sensors.id}"
}

resource "aws_apigatewayv2_route" "bus_position" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /bus-position/{bus_id}"
  target    = "integrations/${aws_apigatewayv2_integration.bus_position.id}"
}

resource "aws_apigatewayv2_route" "bus_position_line" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /bus-position/line/{line_id}"
  target    = "integrations/${aws_apigatewayv2_integration.bus_position.id}"
}

# Lambda permissions for HTTP API
resource "aws_lambda_permission" "people_count_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.people_count_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

resource "aws_lambda_permission" "sensors_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sensors_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

resource "aws_lambda_permission" "bus_position_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bus_position_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

# WebSocket API Gateway
resource "aws_apigatewayv2_api" "websocket" {
  name                       = "bus-simulator-websocket-api"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
  description                = "WebSocket API for real-time bus position updates"

  tags = var.tags
}

resource "aws_apigatewayv2_stage" "websocket" {
  api_id      = aws_apigatewayv2_api.websocket.id
  name        = "production"
  auto_deploy = true

  tags = var.tags
}

# WebSocket integrations
resource "aws_apigatewayv2_integration" "websocket_connect" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.websocket_handler.invoke_arn
}

resource "aws_apigatewayv2_integration" "websocket_disconnect" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.websocket_handler.invoke_arn
}

resource "aws_apigatewayv2_integration" "websocket_default" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.websocket_handler.invoke_arn
}

# WebSocket routes
resource "aws_apigatewayv2_route" "websocket_connect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_connect.id}"
}

resource "aws_apigatewayv2_route" "websocket_disconnect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_disconnect.id}"
}

resource "aws_apigatewayv2_route" "websocket_default" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.websocket_default.id}"
}

# Lambda permissions for WebSocket API
resource "aws_lambda_permission" "websocket_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.websocket_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/*"
}
