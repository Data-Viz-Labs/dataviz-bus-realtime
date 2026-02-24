# MCP Server module for Madrid Bus Real-Time Simulator
# Creates ECS task definition and service for MCP server deployment

# Data source for current region
data "aws_region" "current" {}

# ECS task definition for MCP server
resource "aws_ecs_task_definition" "mcp_server" {
  family                   = "mcp-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = aws_iam_role.mcp_task_role.arn

  container_definitions = jsonencode([{
    name  = "mcp-server"
    image = "${var.ecr_repository_url}:mcp-server-latest"

    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    environment = [
      {
        name  = "TIMESTREAM_DATABASE"
        value = var.timestream_database_name
      },
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.id
      },
      {
        name  = "SECRET_ID"
        value = var.api_key_secret_id
      },
      {
        name  = "LOG_LEVEL"
        value = var.log_level
      },
      {
        name  = "PORT"
        value = tostring(var.container_port)
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = data.aws_region.current.id
        "awslogs-stream-prefix" = "ecs"
      }
    }

    healthCheck = {
      command = [
        "CMD-SHELL",
        "python -c 'import socket; s=socket.socket(); s.connect((\"localhost\", ${var.container_port})); s.close()' || exit 1"
      ]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])

  tags = var.tags
}

# Service Discovery namespace for internal DNS resolution
resource "aws_service_discovery_private_dns_namespace" "mcp" {
  name        = "mcp.local"
  description = "Private DNS namespace for MCP server"
  vpc         = var.vpc_id

  tags = var.tags
}

# Service Discovery service for MCP server
resource "aws_service_discovery_service" "mcp_server" {
  name = "mcp-server"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.mcp.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    # failure_threshold is deprecated and always set to 1 by AWS
    # Removed to avoid deprecation warning
  }

  tags = var.tags
}

# ECS service for MCP server
resource "aws_ecs_service" "mcp_server" {
  name            = "mcp-server"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.mcp_server.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = false
  }

  # Register with Service Discovery
  service_registries {
    registry_arn = aws_service_discovery_service.mcp_server.arn
  }

  # Register with NLB Target Group
  load_balancer {
    target_group_arn = aws_lb_target_group.mcp.arn
    container_name   = "mcp-server"
    container_port   = var.container_port
  }

  # Enable ECS Exec for debugging (optional)
  enable_execute_command = var.enable_execute_command

  # Ensure NLB is created before service
  depends_on = [aws_lb_listener.mcp]

  tags = var.tags
}


# Network Load Balancer for VPC Link integration
resource "aws_lb" "mcp" {
  name               = "mcp-server-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.private_subnet_ids

  enable_deletion_protection = false

  tags = var.tags
}

# Target Group for NLB
resource "aws_lb_target_group" "mcp" {
  name        = "mcp-server-tg"
  port        = var.container_port
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 10
    interval            = 30
    protocol            = "TCP"
  }

  deregistration_delay = 30

  tags = var.tags
}

# NLB Listener
resource "aws_lb_listener" "mcp" {
  load_balancer_arn = aws_lb.mcp.arn
  port              = var.container_port
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }

  tags = var.tags
}

# VPC Link for API Gateway to connect to ECS service in private subnet
resource "aws_apigatewayv2_vpc_link" "mcp" {
  name               = "mcp-server-vpc-link"
  security_group_ids = [var.vpc_link_security_group_id]
  subnet_ids         = var.private_subnet_ids

  tags = var.tags
}

# HTTP API Gateway for MCP server
resource "aws_apigatewayv2_api" "mcp" {
  name          = "mcp-server-api"
  protocol_type = "HTTP"
  description   = "HTTP API Gateway for MCP Server with VPC Link integration"

  cors_configuration {
    allow_origins = var.cors_allowed_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["content-type", "x-api-key", "x-group-name", "authorization"]
    max_age       = 300
  }

  tags = var.tags
}

# HTTP API Authorizer using existing REST authorizer Lambda
resource "aws_apigatewayv2_authorizer" "mcp" {
  api_id           = aws_apigatewayv2_api.mcp.id
  authorizer_type  = "REQUEST"
  # For HTTP APIs, use the invoke ARN directly (not the function ARN)
  authorizer_uri   = var.rest_authorizer_invoke_arn
  identity_sources = ["$request.header.x-api-key", "$request.header.x-group-name"]
  name             = "mcp-api-key-authorizer"

  # Authorizer payload format version for HTTP APIs
  authorizer_payload_format_version = "2.0"

  # Enable simple responses (boolean allow/deny)
  enable_simple_responses = false

  # Cache authorization results for 5 minutes
  authorizer_result_ttl_in_seconds = 300
}

# Lambda permission for HTTP API Authorizer
resource "aws_lambda_permission" "mcp_authorizer" {
  statement_id  = "AllowMCPAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.rest_authorizer_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.mcp.execution_arn}/authorizers/${aws_apigatewayv2_authorizer.mcp.id}"
}

# HTTP API Integration with VPC Link using NLB
resource "aws_apigatewayv2_integration" "mcp" {
  api_id           = aws_apigatewayv2_api.mcp.id
  integration_type = "HTTP_PROXY"

  # Use NLB listener ARN for VPC Link integration
  integration_uri = aws_lb_listener.mcp.arn

  integration_method = "ANY"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.mcp.id

  # Timeout for integration (max 30 seconds for HTTP APIs)
  timeout_milliseconds = 30000

  # Request parameters to pass through
  request_parameters = {
    "overwrite:path" = "$request.path"
  }
}

# Default route (catch-all) with authorizer
resource "aws_apigatewayv2_route" "mcp_default" {
  api_id             = aws_apigatewayv2_api.mcp.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.mcp.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.mcp.id
}

# Health check route (no authorization required)
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.mcp.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.mcp.id}"
}

# MCP protocol routes with authorization
resource "aws_apigatewayv2_route" "mcp_list_tools" {
  api_id             = aws_apigatewayv2_api.mcp.id
  route_key          = "POST /mcp/list-tools"
  target             = "integrations/${aws_apigatewayv2_integration.mcp.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.mcp.id
}

resource "aws_apigatewayv2_route" "mcp_call_tool" {
  api_id             = aws_apigatewayv2_api.mcp.id
  route_key          = "POST /mcp/call-tool"
  target             = "integrations/${aws_apigatewayv2_integration.mcp.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.mcp.id
}

resource "aws_apigatewayv2_route" "mcp_query" {
  api_id             = aws_apigatewayv2_api.mcp.id
  route_key          = "POST /mcp/query"
  target             = "integrations/${aws_apigatewayv2_integration.mcp.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.mcp.id
}

# Production stage with auto-deploy
resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.mcp.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId       = "$context.requestId"
      ip              = "$context.identity.sourceIp"
      requestTime     = "$context.requestTime"
      httpMethod      = "$context.httpMethod"
      routeKey        = "$context.routeKey"
      status          = "$context.status"
      protocol        = "$context.protocol"
      responseLength  = "$context.responseLength"
      errorMessage    = "$context.error.message"
      authorizerError = "$context.authorizer.error"
    })
  }

  default_route_settings {
    throttling_burst_limit = var.throttling_burst_limit
    throttling_rate_limit  = var.throttling_rate_limit
  }

  tags = var.tags
}

# CloudWatch Log Group for API Gateway access logs
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/mcp-server"
  retention_in_days = 7

  tags = var.tags
}
