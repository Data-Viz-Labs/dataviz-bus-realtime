# Minimal test configuration to verify API key functionality
# This creates a simple API with one method and one API key to test

resource "aws_api_gateway_rest_api" "test" {
  name        = "test-api-key-validation"
  description = "Minimal API to test API key functionality"
}

resource "aws_api_gateway_resource" "test" {
  rest_api_id = aws_api_gateway_rest_api.test.id
  parent_id   = aws_api_gateway_rest_api.test.root_resource_id
  path_part   = "test"
}

resource "aws_api_gateway_method" "test" {
  rest_api_id      = aws_api_gateway_rest_api.test.id
  resource_id      = aws_api_gateway_resource.test.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "test" {
  rest_api_id = aws_api_gateway_rest_api.test.id
  resource_id = aws_api_gateway_resource.test.id
  http_method = aws_api_gateway_method.test.http_method
  type        = "MOCK"
  
  request_templates = {
    "application/json" = jsonencode({
      statusCode = 200
    })
  }
}

resource "aws_api_gateway_method_response" "test" {
  rest_api_id = aws_api_gateway_rest_api.test.id
  resource_id = aws_api_gateway_resource.test.id
  http_method = aws_api_gateway_method.test.http_method
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "test" {
  rest_api_id = aws_api_gateway_rest_api.test.id
  resource_id = aws_api_gateway_resource.test.id
  http_method = aws_api_gateway_method.test.http_method
  status_code = aws_api_gateway_method_response.test.status_code

  response_templates = {
    "application/json" = jsonencode({
      message = "API key test successful"
    })
  }
}

resource "aws_api_gateway_deployment" "test" {
  rest_api_id = aws_api_gateway_rest_api.test.id

  depends_on = [
    aws_api_gateway_integration.test
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "test" {
  deployment_id = aws_api_gateway_deployment.test.id
  rest_api_id   = aws_api_gateway_rest_api.test.id
  stage_name    = "test"
}

resource "aws_api_gateway_api_key" "test" {
  name    = "test-key"
  enabled = true
}

resource "aws_api_gateway_usage_plan" "test" {
  name = "test-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.test.id
    stage  = aws_api_gateway_stage.test.stage_name
  }

  depends_on = [
    aws_api_gateway_stage.test
  ]
}

resource "aws_api_gateway_usage_plan_key" "test" {
  key_id        = aws_api_gateway_api_key.test.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.test.id
}

output "test_api_endpoint" {
  value = "${aws_api_gateway_stage.test.invoke_url}/test"
}

output "test_api_key" {
  value     = aws_api_gateway_api_key.test.value
  sensitive = true
}
