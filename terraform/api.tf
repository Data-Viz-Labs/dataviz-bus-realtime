# HTTP API + MCP server for the hackathon groups: one Lambda behind a function URL. The URL is
# public (authorization NONE); every route but /v1/health checks a group key in the code.

data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${local.repo_root}/lambdas/api"
  output_path = "${path.module}/.build/api.zip"
  excludes    = ["__pycache__", "__pycache__/*"]
}

data "aws_iam_policy_document" "api_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.api_assume.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "api" {
  statement {
    sid = "Athena"
    actions = [
      "athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
      "athena:StopQueryExecution", "athena:GetWorkGroup",
    ]
    resources = [aws_athena_workgroup.history.arn]
  }
  statement {
    sid     = "Catalog"
    actions = ["glue:GetDatabase", "glue:GetTable", "glue:GetTables", "glue:GetPartition", "glue:GetPartitions"]
    resources = [
      "arn:aws:glue:${var.aws_region}:${local.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:database/${aws_glue_catalog_database.history.name}",
      "arn:aws:glue:${var.aws_region}:${local.account_id}:table/${aws_glue_catalog_database.history.name}/*",
    ]
  }
  statement {
    sid       = "ReadHistory"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/history/*"]
  }
  statement {
    sid       = "QueryResults"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
    resources = ["${aws_s3_bucket.data.arn}/athena-results/*"]
  }
  statement {
    sid       = "ListHistoryAndResults"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["history/*", "athena-results/*"]
    }
  }
  statement {
    sid       = "BucketLocation"
    actions   = ["s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn, aws_s3_bucket.site.arn]
  }
  statement {
    sid       = "ReadLiveAndNetwork"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/live/*", "${aws_s3_bucket.site.arn}/network.json"]
  }
}

resource "aws_iam_role_policy" "api" {
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name                  = "${local.name}-api"
  description                    = "Madrid bus HTTP API and MCP server"
  role                           = aws_iam_role.api.arn
  runtime                        = "python3.12"
  architectures                  = ["arm64"]
  handler                        = "handler.lambda_handler"
  filename                       = data.archive_file.api.output_path
  source_code_hash               = data.archive_file.api.output_base64sha256
  memory_size                    = 1024
  timeout                        = 60 # Athena queries are polled for up to 50 s
  reserved_concurrent_executions = 20 # caps the cost of a runaway client

  environment {
    variables = {
      DATA_BUCKET      = aws_s3_bucket.data.id
      SITE_BUCKET      = aws_s3_bucket.site.id
      GLUE_DATABASE    = aws_glue_catalog_database.history.name
      ATHENA_WORKGROUP = aws_athena_workgroup.history.name
      KEY_HASHES       = local.group_key_hashes
    }
  }

  depends_on = [aws_cloudwatch_log_group.api, aws_iam_role_policy_attachment.api_logs]
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # keys are checked in the code

  cors {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type", "x-api-key", "authorization", "mcp-protocol-version"]
    max_age       = 3600
  }
}

# A public function URL needs both permissions (lambda:InvokeFunction since October 2025).
resource "aws_lambda_permission" "api_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "api_invoke" {
  statement_id             = "AllowPublicInvokeViaFunctionUrl"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api.function_name
  principal                = "*"
  invoked_via_function_url = true
}

output "api_url" {
  description = "HTTP API base URL (routes under /v1, docs at <site_url>docs.html)"
  value       = trimsuffix(aws_lambda_function_url.api.function_url, "/")
}

output "mcp_url" {
  description = "MCP server (Streamable HTTP) URL"
  value       = "${trimsuffix(aws_lambda_function_url.api.function_url, "/")}/mcp"
}
