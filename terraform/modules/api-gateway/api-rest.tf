# REST API Gateway (v1) for API key authentication support
resource "aws_api_gateway_rest_api" "main" {
  name        = "bus-simulator-rest-api"
  description = "REST API for Madrid Bus Real-Time Simulator with API key authentication"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

# API Gateway deployment with automatic redeployment trigger
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha256(jsonencode([
      aws_api_gateway_rest_api.main.body,
      aws_api_gateway_resource.people_count.id,
      aws_api_gateway_resource.sensors.id,
      aws_api_gateway_resource.bus_position.id,
      aws_api_gateway_method.people_count.id,
      aws_api_gateway_method.sensors.id,
      aws_api_gateway_method.bus_position.id,
      aws_api_gateway_method.bus_position_line.id,
      aws_api_gateway_integration.people_count.id,
      aws_api_gateway_integration.sensors.id,
      aws_api_gateway_integration.bus_position.id,
      aws_api_gateway_integration.bus_position_line.id,
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
  stage_name    = "v1"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_access_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
      errorType      = "$context.error.messageString"
    })
  }

  # Enable detailed CloudWatch metrics and execution logging
  xray_tracing_enabled = true

  tags = var.tags
}

# Method settings for execution logging
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = true
  }
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
