# API Gateway module for Madrid Bus Real-Time Simulator
# Creates REST API with API key authentication and WebSocket API with Lambda integrations

# Lambda functions
resource "aws_lambda_function" "people_count_api" {
  filename         = "${path.root}/../build/people_count_api.zip"
  function_name    = "bus-simulator-people-count"
  role             = var.lambda_execution_role_arn
  handler          = "people_count_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/people_count_api.zip")
  runtime          = "python3.11"
  timeout          = 30

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
  role             = var.lambda_execution_role_arn
  handler          = "sensors_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/sensors_api.zip")
  runtime          = "python3.11"
  timeout          = 30

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
  role             = var.lambda_execution_role_arn
  handler          = "bus_position_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/bus_position_api.zip")
  runtime          = "python3.11"
  timeout          = 30

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
  role             = var.lambda_execution_role_arn
  handler          = "websocket_handler.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/websocket_handler.zip")
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
    }
  }

  tags = var.tags
}

# REST API Gateway (v1) for API key authentication support
resource "aws_api_gateway_rest_api" "main" {
  name        = "bus-simulator-rest-api"
  description = "REST API for Madrid Bus Real-Time Simulator with API key authentication"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

# API Gateway deployment
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Force redeployment when routes change
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.people_count.id,
      aws_api_gateway_resource.sensors.id,
      aws_api_gateway_resource.sensors_entity_type.id,
      aws_api_gateway_resource.sensors_entity_id.id,
      aws_api_gateway_resource.bus_position.id,
      aws_api_gateway_resource.bus_position_id.id,
      aws_api_gateway_resource.bus_position_line.id,
      aws_api_gateway_resource.bus_position_line_id.id,
      aws_api_gateway_method.people_count.id,
      aws_api_gateway_method.sensors.id,
      aws_api_gateway_method.bus_position.id,
      aws_api_gateway_method.bus_position_line.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway stage
resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "prod"

  tags = var.tags
}

# Enable CORS via Gateway Response
resource "aws_api_gateway_gateway_response" "cors" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "DEFAULT_4XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
  }
}

resource "aws_api_gateway_gateway_response" "cors_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "DEFAULT_5XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
  }
}

# API Resources - People Count
resource "aws_api_gateway_resource" "people_count" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "people-count"
}

resource "aws_api_gateway_resource" "people_count_stop_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.people_count.id
  path_part   = "{stop_id}"
}

# API Resources - Sensors
resource "aws_api_gateway_resource" "sensors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "sensors"
}

resource "aws_api_gateway_resource" "sensors_entity_type" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.sensors.id
  path_part   = "{entity_type}"
}

resource "aws_api_gateway_resource" "sensors_entity_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.sensors_entity_type.id
  path_part   = "{entity_id}"
}

# API Resources - Bus Position
resource "aws_api_gateway_resource" "bus_position" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "bus-position"
}

resource "aws_api_gateway_resource" "bus_position_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.bus_position.id
  path_part   = "{bus_id}"
}

resource "aws_api_gateway_resource" "bus_position_line" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.bus_position.id
  path_part   = "line"
}

resource "aws_api_gateway_resource" "bus_position_line_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.bus_position_line.id
  path_part   = "{line_id}"
}

# API Methods - People Count
resource "aws_api_gateway_method" "people_count" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.people_count_stop_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.path.stop_id" = true
  }
}

resource "aws_api_gateway_integration" "people_count" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.people_count_stop_id.id
  http_method = aws_api_gateway_method.people_count.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.people_count_api.invoke_arn
}

# API Methods - Sensors
resource "aws_api_gateway_method" "sensors" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.sensors_entity_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.path.entity_type" = true
    "method.request.path.entity_id"   = true
  }
}

resource "aws_api_gateway_integration" "sensors" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.sensors_entity_id.id
  http_method = aws_api_gateway_method.sensors.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.sensors_api.invoke_arn
}

# API Methods - Bus Position (by bus_id)
resource "aws_api_gateway_method" "bus_position" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.bus_position_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.path.bus_id" = true
  }
}

resource "aws_api_gateway_integration" "bus_position" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.bus_position_id.id
  http_method = aws_api_gateway_method.bus_position.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.bus_position_api.invoke_arn
}

# API Methods - Bus Position (by line_id)
resource "aws_api_gateway_method" "bus_position_line" {
  rest_api_id      = aws_api_gateway_rest_api.main.id
  resource_id      = aws_api_gateway_resource.bus_position_line_id.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.path.line_id" = true
  }
}

resource "aws_api_gateway_integration" "bus_position_line" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.bus_position_line_id.id
  http_method = aws_api_gateway_method.bus_position_line.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.bus_position_api.invoke_arn
}

# Lambda permissions for REST API
resource "aws_lambda_permission" "people_count_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.people_count_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "sensors_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sensors_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "bus_position_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bus_position_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# API Keys for hackathon participants
resource "aws_api_gateway_api_key" "participant_keys" {
  count = var.participant_count
  name  = "participant-${count.index + 1}"

  tags = var.tags
}

# Usage Plan with rate limiting and quotas
resource "aws_api_gateway_usage_plan" "hackathon" {
  name        = "hackathon-usage-plan"
  description = "Usage plan for hackathon participants with rate limiting"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = 10000
    period = "DAY"
  }

  throttle_settings {
    burst_limit = 100
    rate_limit  = 50
  }

  tags = var.tags
}

# Associate API keys with usage plan
resource "aws_api_gateway_usage_plan_key" "participant_keys" {
  count         = var.participant_count
  key_id        = aws_api_gateway_api_key.participant_keys[count.index].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.hackathon.id
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
