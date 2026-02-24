# Custom Authorizers for REST and WebSocket APIs
# Validate API keys against Secrets Manager and enforce x-group-name header

# REST API Custom Authorizer Lambda Function
resource "aws_lambda_function" "rest_authorizer" {
  filename      = "${path.module}/../../../build/rest_authorizer.zip"
  function_name = "bus-simulator-rest-authorizer"
  role          = aws_iam_role.authorizer.arn
  handler       = "authorizer_rest.lambda_handler"
  runtime       = "python3.11"
  timeout       = 10
  memory_size   = 128

  source_code_hash = fileexists("${path.module}/../../../build/rest_authorizer.zip") ? filebase64sha256("${path.module}/../../../build/rest_authorizer.zip") : null

  environment {
    variables = {
      SECRET_ID = aws_secretsmanager_secret.api_key.id
    }
  }

  tags = var.tags
}

# WebSocket API Custom Authorizer Lambda Function
resource "aws_lambda_function" "websocket_authorizer_v2" {
  filename      = "${path.module}/../../../build/websocket_authorizer_v2.zip"
  function_name = "bus-simulator-websocket-authorizer-v2"
  role          = aws_iam_role.authorizer.arn
  handler       = "authorizer_websocket.lambda_handler"
  runtime       = "python3.11"
  timeout       = 10
  memory_size   = 128

  source_code_hash = fileexists("${path.module}/../../../build/websocket_authorizer_v2.zip") ? filebase64sha256("${path.module}/../../../build/websocket_authorizer_v2.zip") : null

  environment {
    variables = {
      SECRET_ID = aws_secretsmanager_secret.api_key.id
    }
  }

  tags = var.tags
}

# IAM Role for Custom Authorizers
resource "aws_iam_role" "authorizer" {
  name = "bus-simulator-authorizer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

# IAM Policy for Secrets Manager access
resource "aws_iam_role_policy" "authorizer_secrets" {
  name = "authorizer-secrets-access"
  role = aws_iam_role.authorizer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = aws_secretsmanager_secret.api_key.arn
    }]
  })
}

# Attach basic execution role for CloudWatch Logs
resource "aws_iam_role_policy_attachment" "authorizer_logs" {
  role       = aws_iam_role.authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# REST API Gateway Authorizer
resource "aws_api_gateway_authorizer" "rest" {
  name        = "rest-api-key-authorizer"
  rest_api_id = aws_api_gateway_rest_api.main.id
  authorizer_uri = aws_lambda_function.rest_authorizer.invoke_arn
  type        = "REQUEST"

  # Cache authorization results for 5 minutes
  authorizer_result_ttl_in_seconds = 300

  # Identity sources for caching
  identity_source = "method.request.header.x-api-key,method.request.header.x-group-name"
}

# Lambda permission for REST Authorizer
resource "aws_lambda_permission" "rest_authorizer" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rest_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/authorizers/${aws_api_gateway_authorizer.rest.id}"
}

# Update WebSocket Authorizer to use new Custom Authorizer
# Note: authorizer_result_ttl_in_seconds is not supported for WebSocket APIs
resource "aws_apigatewayv2_authorizer" "websocket_v2" {
  api_id           = aws_apigatewayv2_api.websocket.id
  authorizer_type  = "REQUEST"
  authorizer_uri   = aws_lambda_function.websocket_authorizer_v2.invoke_arn
  identity_sources = ["route.request.querystring.api_key", "route.request.querystring.group_name"]
  name             = "websocket-api-key-authorizer-v2"
}

# Lambda permission for WebSocket Authorizer V2
resource "aws_lambda_permission" "websocket_authorizer_v2" {
  statement_id  = "AllowAPIGatewayInvokeV2"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.websocket_authorizer_v2.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/authorizers/${aws_apigatewayv2_authorizer.websocket_v2.id}"
}
