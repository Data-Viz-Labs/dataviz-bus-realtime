# Real-time MQTT feed: the simulator publishes per-line topics (madrid/lines/<line>/state|calls)
# through the IoT data plane; hackathon groups subscribe over MQTT/WSS with their access key,
# checked by a custom authorizer that only allows subscribing to madrid/*.

data "aws_iot_endpoint" "data" {
  endpoint_type = "iot:Data-ATS"
}

locals {
  mqtt_endpoint        = data.aws_iot_endpoint.data.endpoint_address
  mqtt_authorizer_name = "${local.name}-groups"
}

data "archive_file" "iot_authorizer" {
  type        = "zip"
  source_dir  = "${local.repo_root}/src/lambda/iot-authorizer"
  output_path = "${path.module}/.build/iot_authorizer.zip"
  excludes    = ["__pycache__", "__pycache__/*"]
}

data "aws_iam_policy_document" "iot_authorizer_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "iot_authorizer" {
  name               = "${local.name}-iot-authorizer"
  assume_role_policy = data.aws_iam_policy_document.iot_authorizer_assume.json
}

resource "aws_iam_role_policy_attachment" "iot_authorizer_logs" {
  role       = aws_iam_role.iot_authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "iot_authorizer" {
  name              = "/aws/lambda/${local.name}-iot-authorizer"
  retention_in_days = 14
}

resource "aws_lambda_function" "iot_authorizer" {
  function_name    = "${local.name}-iot-authorizer"
  role             = aws_iam_role.iot_authorizer.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  filename         = data.archive_file.iot_authorizer.output_path
  source_code_hash = data.archive_file.iot_authorizer.output_base64sha256
  memory_size      = 128
  timeout          = 5 # IoT Core's limit for custom authorizers

  environment {
    variables = {
      KEY_HASHES = local.group_key_hashes
    }
  }

  depends_on = [aws_cloudwatch_log_group.iot_authorizer, aws_iam_role_policy_attachment.iot_authorizer_logs]
}

resource "aws_iot_authorizer" "groups" {
  name                    = local.mqtt_authorizer_name
  authorizer_function_arn = aws_lambda_function.iot_authorizer.arn
  signing_disabled        = true
  status                  = "ACTIVE"
  enable_caching_for_http = true
}

resource "aws_lambda_permission" "iot_authorizer" {
  statement_id   = "AllowIotCustomAuthorizer"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.iot_authorizer.function_name
  principal      = "iot.amazonaws.com"
  source_arn     = aws_iot_authorizer.groups.arn
  source_account = local.account_id
}

data "aws_iam_policy_document" "simulator_mqtt" {
  statement {
    sid       = "PublishFeed"
    actions   = ["iot:Publish"]
    resources = ["arn:aws:iot:${var.aws_region}:${local.account_id}:topic/madrid/*"]
  }
  statement {
    sid       = "FindEndpoint"
    actions   = ["iot:DescribeEndpoint"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "simulator_mqtt" {
  name   = "mqtt"
  role   = aws_iam_role.simulator.id
  policy = data.aws_iam_policy_document.simulator_mqtt.json
}

output "mqtt_endpoint" {
  description = "AWS IoT Core data endpoint (MQTT_ENDPOINT)"
  value       = local.mqtt_endpoint
}

output "mqtt_authorizer_name" {
  description = "Custom authorizer students pass as x-amz-customauthorizer-name"
  value       = aws_iot_authorizer.groups.name
}

output "mqtt_websocket_url" {
  description = "MQTT over WebSockets; append ?x-amz-customauthorizer-name=<name>&token=<key>"
  value       = "wss://${local.mqtt_endpoint}/mqtt"
}
