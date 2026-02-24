# IAM roles and policies for MCP Server ECS task
# Requirements: 14.8, 14.13, 14.15

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# IAM role for MCP server ECS task
# This role allows the MCP server container to access AWS services
resource "aws_iam_role" "mcp_task_role" {
  name               = "mcp-server-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json

  tags = var.tags
}

# Trust policy allowing ECS tasks to assume this role
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Policy for reading from Secrets Manager
# Requirement 14.8: MCP server validates API Key by reading from Secrets Manager
data "aws_iam_policy_document" "secrets_manager_read" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]

    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:secret:bus-simulator/api-key-*"
    ]
  }
}

resource "aws_iam_policy" "secrets_manager_read" {
  name        = "mcp-server-secrets-manager-read"
  description = "Allow MCP server to read API key from Secrets Manager"
  policy      = data.aws_iam_policy_document.secrets_manager_read.json

  tags = var.tags
}

# Policy for querying Timestream database
# Requirement 14.13: Task definition includes environment variables for accessing Timestream_DB
data "aws_iam_policy_document" "timestream_query" {
  statement {
    effect = "Allow"

    actions = [
      "timestream:DescribeEndpoints",
      "timestream:Select",
      "timestream:DescribeTable",
      "timestream:ListMeasures"
    ]

    resources = [
      "arn:aws:timestream:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:database/${var.timestream_database_name}",
      "arn:aws:timestream:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:database/${var.timestream_database_name}/table/*"
    ]
  }

  # DescribeEndpoints requires wildcard resource
  statement {
    effect = "Allow"

    actions = [
      "timestream:DescribeEndpoints"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "timestream_query" {
  name        = "mcp-server-timestream-query"
  description = "Allow MCP server to query Timestream database"
  policy      = data.aws_iam_policy_document.timestream_query.json

  tags = var.tags
}

# Policy for writing to CloudWatch Logs
# Requirement 14.13: Task definition includes environment variables for accessing CloudWatch
data "aws_iam_policy_document" "cloudwatch_logs_write" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_name}:*"
    ]
  }
}

resource "aws_iam_policy" "cloudwatch_logs_write" {
  name        = "mcp-server-cloudwatch-logs-write"
  description = "Allow MCP server to write logs to CloudWatch"
  policy      = data.aws_iam_policy_document.cloudwatch_logs_write.json

  tags = var.tags
}

# Attach policies to the task role
resource "aws_iam_role_policy_attachment" "secrets_manager_read" {
  role       = aws_iam_role.mcp_task_role.name
  policy_arn = aws_iam_policy.secrets_manager_read.arn
}

resource "aws_iam_role_policy_attachment" "timestream_query" {
  role       = aws_iam_role.mcp_task_role.name
  policy_arn = aws_iam_policy.timestream_query.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs_write" {
  role       = aws_iam_role.mcp_task_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs_write.arn
}
