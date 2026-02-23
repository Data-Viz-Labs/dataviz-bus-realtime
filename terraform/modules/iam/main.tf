# IAM module for Madrid Bus Real-Time Simulator
# Creates IAM roles and policies for Lambda and Fargate services

# Lambda execution role
resource "aws_iam_role" "lambda_execution" {
  name = "bus-simulator-lambda-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Lambda execution policy - CloudWatch Logs
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda policy - Timestream read access
resource "aws_iam_role_policy" "lambda_timestream_read" {
  name = "timestream-read-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "timestream:DescribeEndpoints"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "timestream:Select",
          "timestream:DescribeTable",
          "timestream:ListMeasures"
        ]
        Resource = concat(
          [var.timestream_database_arn],
          var.timestream_table_arns
        )
      }
    ]
  })
}

# Lambda policy - DynamoDB access for WebSocket connections
resource "aws_iam_role_policy" "lambda_dynamodb_access" {
  name = "dynamodb-websocket-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# Lambda policy - API Gateway Management API for WebSocket
resource "aws_iam_role_policy" "lambda_apigateway_management" {
  name = "apigateway-management-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "arn:aws:execute-api:*:*:*/@connections/*"
      }
    ]
  })
}

# Fargate task role
resource "aws_iam_role" "ecs_task" {
  name = "bus-simulator-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Fargate task policy - Timestream write access
resource "aws_iam_role_policy" "ecs_timestream_write" {
  name = "timestream-write-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "timestream:DescribeEndpoints"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "timestream:WriteRecords"
        ]
        Resource = concat(
          [var.timestream_database_arn],
          var.timestream_table_arns
        )
      }
    ]
  })
}

# Fargate task policy - EventBridge publish access
resource "aws_iam_role_policy" "ecs_eventbridge_publish" {
  name = "eventbridge-publish-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = var.eventbridge_bus_arn
      }
    ]
  })
}

# Fargate task policy - S3 read access for configuration
resource "aws_iam_role_policy" "ecs_s3_read" {
  name = "s3-config-read-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.config_bucket_arn,
          "${var.config_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Fargate execution role
resource "aws_iam_role" "ecs_execution" {
  name = "bus-simulator-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Fargate execution policy - ECR and CloudWatch Logs
resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Fargate execution policy - ECR pull access
resource "aws_iam_role_policy" "ecs_ecr_pull" {
  name = "ecr-pull-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arn
      }
    ]
  })
}

# API Gateway CloudWatch Logs role
resource "aws_iam_role" "apigateway_cloudwatch" {
  name = "bus-simulator-apigateway-cloudwatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# API Gateway CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "apigateway_cloudwatch" {
  role       = aws_iam_role.apigateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

# API Gateway account settings - CloudWatch Logs role
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.apigateway_cloudwatch.arn
}
